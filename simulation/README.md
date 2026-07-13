# Simulation

Off-robot simulation for developing and validating the maze-solving and motion
logic before running on hardware:

- Maze representation + solver (e.g. flood-fill / modified Dijkstra) with a
  simulated 16×16 maze.
- Motion model for the N20-driven differential base to tune search vs. speed runs.
- Sensor model for the IR wall-detection array to test cell-edge decisions.

Ideally shares the solver/planner core with [`../fw`](../fw) so the same code runs
in sim and on the STM32.

_Not yet implemented — placeholder for the simulation sources._
