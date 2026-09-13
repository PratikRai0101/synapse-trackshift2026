from src.f1_data import get_race_telemetry, enable_cache, get_circuit_rotation, load_session, get_quali_telemetry, list_rounds, list_sprints
from src.run_session import run_arcade_replay, launch_insights_menu
from src.interfaces.qualifying import run_qualifying_replay
import sys
from src.cli.race_selection import cli_load
from src.gui.race_selection import RaceSelectionWindow
from PySide6.QtWidgets import QApplication
from src.lib.season import get_season
import logging
import os


def _example_lap_from_cached_frames(race_telemetry):
  """Reconstruct display geometry when FastF1 session data is unavailable."""
  import pandas as pd

  frames = race_telemetry.get('frames', [])
  driver = next((code for frame in frames for code in frame.get('drivers', {})), None)
  if driver is None:
    return None
  rows = []
  target_lap = None
  last_distance = -1.0
  for frame in frames:
    sample = frame.get('drivers', {}).get(driver)
    if not sample:
      continue
    lap = int(sample.get('lap', 0) or 0)
    if target_lap is None and lap > 0:
      target_lap = lap
    if lap != target_lap:
      if rows:
        break
      continue
    distance = float(sample.get('dist', 0.0) or 0.0)
    if distance <= last_distance:
      continue
    rows.append({
      'X': float(sample.get('x', 0.0) or 0.0),
      'Y': float(sample.get('y', 0.0) or 0.0),
      'Distance': distance,
      'Speed': float(sample.get('speed', 0.0) or 0.0),
      'DRS': int(sample.get('drs', 0) or 0),
    })
    last_distance = distance
  return pd.DataFrame(rows) if len(rows) >= 2 else None

def _rotation_from_cached_geometry(example_lap):
  """Orient cached geometry from its start/finish straight.

  FastF1's display convention points the opening straight to the left. When
  circuit metadata is unavailable, the first 400 m provides the same stable
  orientation without a circuit-specific hard-coded angle.
  """
  import math
  import numpy as np

  if example_lap is None or not {"X", "Y", "Distance"}.issubset(example_lap):
    return 0.0
  points = example_lap[["X", "Y", "Distance"]].dropna().sort_values("Distance")
  if len(points) < 2:
    return 0.0
  start_distance = float(points["Distance"].iloc[0])
  opening = points[points["Distance"] <= start_distance + 400.0]
  if len(opening) < 2:
    opening = points.iloc[:min(20, len(points))]
  dx = float(opening["X"].iloc[-1] - opening["X"].iloc[0])
  dy = float(opening["Y"].iloc[-1] - opening["Y"].iloc[0])
  if not np.isfinite(dx) or not np.isfinite(dy) or math.hypot(dx, dy) < 1e-6:
    return 0.0
  rotation = 180.0 - math.degrees(math.atan2(dy, dx))
  return (rotation + 180.0) % 360.0 - 180.0


def _release_ready_file(ready_file):
  """Signal the launching GUI that startup finished, even on failure.

  The race-selection window polls for this file to close its modal loading
  dialog, so writing it on the error path is what prevents an apparent hang.
  """
  if not ready_file:
    return
  try:
    with open(ready_file, "w") as handle:
      handle.write("failed")
  except OSError:
    pass


def main(year=None, round_number=None, playback_speed=1, session_type='R', visible_hud=True, ready_file=None, show_telemetry_viewer=True):
  print(f"Loading F1 {year} Round {round_number} Session '{session_type}'")
  try:
    session = load_session(year, round_number, session_type)
  except Exception as exc:
    # Fail loudly and actionably: a stack trace here previously looked like a
    # frozen GUI because the loading dialog waited on a process that died.
    print(f"\nCould not load {year} round {round_number} session '{session_type}'.")
    print(f"  {exc}")
    print("\nTry a completed event, e.g.:")
    print(f"  python main.py --viewer --year {year} --round <completed-round>")
    _release_ready_file(ready_file)
    raise SystemExit(2)

  print(f"Loaded session: {session.event['EventName']} - {session.event['RoundNumber']} - {session_type}")

  # Enable cache for fastf1
  enable_cache()

  if session_type == 'Q' or session_type == 'SQ':

    # Get the drivers who participated and their lap times

    qualifying_session_data = get_quali_telemetry(session, session_type=session_type)

    # Run the arcade screen showing qualifying results

    title = f"{session.event['EventName']} - {'Sprint Qualifying' if session_type == 'SQ' else 'Qualifying Results'}"
    
    run_qualifying_replay(
      session=session,
      data=qualifying_session_data,
      title=title,
      ready_file=ready_file,
    )

  else:

    # Get the drivers who participated in the race

    race_telemetry = get_race_telemetry(session, session_type=session_type)

    # Get example lap for track layout
    # Qualifying lap preferred for DRS zones (fallback to fastest race lap (no DRS data))
    example_lap = None
    
    try:
        print("Attempting to load qualifying session for track layout...")
        quali_session = load_session(year, round_number, 'Q')
        if quali_session is not None and len(quali_session.laps) > 0:
            fastest_quali = quali_session.laps.pick_fastest()
            if fastest_quali is not None:
                quali_telemetry = fastest_quali.get_telemetry()
                if 'DRS' in quali_telemetry.columns:
                    example_lap = quali_telemetry
                    print(f"Using qualifying lap from driver {fastest_quali['Driver']} for DRS Zones")
    except Exception as e:
        print(f"Could not load qualifying session: {e}")

    # fallback: Use fastest race lap
    if example_lap is None:
        try:
            fastest_lap = session.laps.pick_fastest()
            if fastest_lap is not None:
                example_lap = fastest_lap.get_telemetry()
                print("Using fastest race lap (DRS detection may use speed-based fallback)")
        except Exception as exc:
            print(f"Race lap telemetry unavailable: {exc}")
    if example_lap is None:
        example_lap = _example_lap_from_cached_frames(race_telemetry)
        if example_lap is not None:
            print("Reconstructed track layout from cached public replay frames")
        else:
            print("Error: No valid track geometry found")
            return

    drivers = list(session.drivers)
    if not drivers and race_telemetry.get('frames'):
        drivers = list(race_telemetry['frames'][0].get('drivers', {}))

    # Get circuit rotation

    try:
      circuit_rotation = get_circuit_rotation(session)
    except Exception as exc:
      circuit_rotation = _rotation_from_cached_geometry(example_lap)
      print(
        f"Circuit metadata unavailable; inferred cached orientation "
        f"({circuit_rotation:.1f}°): {exc}"
      )
    
    # Prepare session info for display banner
    session_info = {
        'event_name': session.event.get('EventName', ''),
        'circuit_name': session.event.get('Location', ''),  # Circuit location/name
        'country': session.event.get('Country', ''),
        'year': year,
        'round': round_number,
        'date': session.event.get('EventDate', '').strftime('%B %d, %Y') if session.event.get('EventDate') else '',
        'total_laps': race_telemetry['total_laps'],
        'circuit_length_m': float(example_lap["Distance"].max()) if example_lap is not None and "Distance" in example_lap else None,
    }

    # Deterministic Judge Mode scenario bookmarks. Built offline by
    # scripts/build_scenario_bookmarks.py; absent simply means the 5-0 slots
    # stay on the even phase bookmarks.
    try:
        from src.intelligence.scenarios import (
            load_scenario_artifact,
            scenario_artifact_path,
        )

        scenario_targets = load_scenario_artifact(
            scenario_artifact_path(year, round_number)
        )
    except Exception as exc:
        scenario_targets = {}
        print(f"Scenario bookmarks unavailable: {exc}")

    # Launch insights menu (always shown with replay)
    launch_insights_menu()
    print("Launching insights menu...")

    # Run the arcade replay

    run_arcade_replay(
      frames=race_telemetry['frames'],
      track_statuses=race_telemetry['track_statuses'],
      example_lap=example_lap,
      drivers=drivers,
      playback_speed=playback_speed,
      driver_colors=race_telemetry['driver_colors'],
      title=f"{session.event['EventName']} - {'Sprint' if session_type == 'S' else 'Race'}",
      total_laps=race_telemetry['total_laps'],
      circuit_rotation=circuit_rotation,
      visible_hud=visible_hud,
      ready_file=ready_file,
      session_info=session_info,
      session=session,
      scenario_bookmarks=scenario_targets,
      enable_telemetry=True,
      race_control_messages=race_telemetry.get('race_control_messages', [])
    )

if __name__ == "__main__":

  if "--help" in sys.argv or "-h" in sys.argv:
    print("Usage: python main.py [--viewer] [--year YEAR] [--round ROUND] "
          "[--qualifying|--sprint|--sprint-qualifying] [--no-hud] "
          "[--refresh-data] [--ready-file PATH]")
    sys.exit(0)

  # Capture native crashes and uncaught exceptions so failures are diagnosable.
  import faulthandler
  faulthandler.enable()

  def _log_uncaught(exc_type, exc, tb):
    try:
      import datetime, traceback
      os.makedirs("computed_data", exist_ok=True)
      with open(os.path.join("computed_data", "crash.log"), "a") as fh:
        fh.write(f"\n=== {datetime.datetime.now().isoformat()} ===\n")
        traceback.print_exception(exc_type, exc, tb, file=fh)
    except Exception:
      pass
    sys.__excepthook__(exc_type, exc, tb)

  sys.excepthook = _log_uncaught

  # Read early so any later failure can still release the launcher's wait.
  _ready_file_arg = None
  if "--ready-file" in sys.argv:
    _ready_index = sys.argv.index("--ready-file") + 1
    if _ready_index < len(sys.argv):
      _ready_file_arg = sys.argv[_ready_index]

  def _on_uncaught(exc_type, exc, tb):
    _release_ready_file(_ready_file_arg)
    _log_uncaught(exc_type, exc, tb)

  sys.excepthook = _on_uncaught

  if "--verbose" not in sys.argv:# fastf1 logging is disabled by default
    logging.getLogger("fastf1").setLevel(logging.CRITICAL)

  if "--cli" in sys.argv:
    # Run the CLI
    cli_load()
    sys.exit(0)

  if "--year" in sys.argv:
    year_index = sys.argv.index("--year") + 1
    year = int(sys.argv[year_index])
  else:
    year = get_season()  # Default year

  if "--round" in sys.argv:
    round_index = sys.argv.index("--round") + 1
    round_number = int(sys.argv[round_index])
  else:
    round_number = 12  # Default round number

  if "--list-rounds" in sys.argv:
    list_rounds(year)
  elif "--list-sprints" in sys.argv:
    list_sprints(year)
  else:
    playback_speed = 1

  if "--viewer" in sys.argv:
  
    visible_hud = True
    if "--no-hud" in sys.argv:
      visible_hud = False

    # Session type selection
    session_type = 'SQ' if "--sprint-qualifying" in sys.argv else ('S' if "--sprint" in sys.argv else ('Q' if "--qualifying" in sys.argv else 'R'))

    # Optional ready-file path used when spawned from the GUI to signal ready state
    ready_file = _ready_file_arg

    try:
      main(year, round_number, playback_speed, session_type=session_type,
           visible_hud=visible_hud, ready_file=ready_file)
    except SystemExit:
      raise
    except BaseException:
      _release_ready_file(ready_file)
      raise
    sys.exit(0)

  # Run the GUI

  app = QApplication(sys.argv)
  win = RaceSelectionWindow()
  win.show()
  sys.exit(app.exec())