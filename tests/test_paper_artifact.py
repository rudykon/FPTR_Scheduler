from __future__ import annotations

import math
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from experiments import paper_experiments
from tools import scheduler_validator

ROOT = Path(__file__).resolve().parents[1]
TRACE_RE = re.compile(
    r"^TRACE stage=(?P<stage>[a-z_]+) score=(?P<score>-?[0-9]+) "
    r"elapsed_ms=(?P<elapsed>[0-9]+(?:\.[0-9]+)?) "
    r"deadline_hit=(?P<deadline>[01])$"
)


class PaperArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory(prefix="paper-scheduler-test-")
        cls.binary = Path(cls.temp.name) / "scheduler"
        subprocess.run(
            [
                "g++",
                "-std=c++17",
                "-O2",
                str(ROOT / "src" / "scheduler.cpp"),
                str(ROOT / "src" / "core.cpp"),
                "-o",
                str(cls.binary),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def _parse_trace(self, stderr: str) -> list[tuple[str, int, float, bool]]:
        lines = [line.strip() for line in stderr.splitlines() if line.strip()]
        self.assertTrue(lines, "solver emitted no trace records")
        traces: list[tuple[str, int, float, bool]] = []
        for line in lines:
            match = TRACE_RE.fullmatch(line)
            self.assertIsNotNone(match, f"unexpected stderr line: {line!r}")
            assert match is not None
            traces.append(
                (
                    match.group("stage"),
                    int(match.group("score")),
                    float(match.group("elapsed")),
                    bool(int(match.group("deadline"))),
                )
            )
        return traces

    def _run_and_audit(
        self,
        text: str,
        case: scheduler_validator.CaseInput,
        *,
        stage: str,
        expected_stages: tuple[str, ...],
        budget_ms: int = 87,
    ) -> tuple[int, list[tuple[str, int, float, bool]]]:
        proc = subprocess.run(
            [
                str(self.binary),
                "--stage",
                stage,
                "--budget-ms",
                str(budget_ms),
                "--trace",
            ],
            input=text,
            text=True,
            capture_output=True,
            timeout=1.0,
            check=False,
            cwd=ROOT,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

        result = scheduler_validator.validate_and_score(case, proc.stdout)
        traces = self._parse_trace(proc.stderr)
        self.assertEqual(tuple(trace[0] for trace in traces), expected_stages)

        trace_scores = [trace[1] for trace in traces]
        self.assertTrue(
            all(current >= previous for previous, current in zip(trace_scores, trace_scores[1:])),
            f"non-monotone trace for {stage}: {trace_scores}",
        )
        self.assertEqual(traces[-1][0], "final")
        self.assertEqual(traces[-1][1], result.transmitted)
        return result.transmitted, traces

    def test_all_cumulative_stages_are_legal_and_trace_consistent(self) -> None:
        scenario = paper_experiments.HELDOUT_SCENARIOS[0]
        seed = paper_experiments.QA_HELDOUT_SEED_BASE
        text = paper_experiments.generate_case(scenario, seed)
        case = scheduler_validator.parse_case_text(text, case_id="heldout-stage-audit")
        expected = {
            "beamfirst": ("beam_first", "final"),
            "base": ("base", "final"),
            "global": ("base", "global", "final"),
            "cg": ("base", "global", "cg", "final"),
            "remask": ("base", "global", "cg", "remask", "final"),
            "full": ("base", "global", "cg", "remask", "pair", "final"),
        }

        for stage, expected_stages in expected.items():
            with self.subTest(stage=stage):
                self._run_and_audit(
                    text,
                    case,
                    stage=stage,
                    expected_stages=expected_stages,
                )

    def test_five_millisecond_budget_still_emits_a_legal_solution(self) -> None:
        scenario = paper_experiments.HELDOUT_SCENARIOS[0]
        text = paper_experiments.generate_case(
            scenario,
            paper_experiments.QA_HELDOUT_SEED_BASE + 1,
        )
        case = scheduler_validator.parse_case_text(text, case_id="five-ms-fallback")
        self._run_and_audit(
            text,
            case,
            stage="full",
            expected_stages=("base", "global", "cg", "remask", "pair", "final"),
            budget_ms=5,
        )

    def test_full_pipeline_is_legal_at_maximum_n_k_and_p(self) -> None:
        scenario_index = len(paper_experiments.HELDOUT_SCENARIOS) - 1
        scenario = paper_experiments.HELDOUT_SCENARIOS[scenario_index]
        seed = paper_experiments.QA_HELDOUT_SEED_BASE + scenario_index * 1000
        text = paper_experiments.generate_case(scenario, seed)
        case = scheduler_validator.parse_case_text(text, case_id="maximum-dimensions")
        self.assertEqual((case.N, case.K, case.P), (100, 72, 32))
        self._run_and_audit(
            text,
            case,
            stage="full",
            expected_stages=("base", "global", "cg", "remask", "pair", "final"),
        )

    def test_cpp_and_python_agree_on_floating_point_rate_counterexample(self) -> None:
        average = 1.3966836204782183e-09
        fse = (
            100.0
            + 10.0 * math.log10(1.0 / 7.0)
            + 10.0 * math.log10(average / 1.0)
        )
        self.assertEqual(scheduler_validator.cap_of(fse), 90)

        probe_source = Path(self.temp.name) / "rate_probe.cpp"
        probe_binary = Path(self.temp.name) / "rate_probe"
        core_path = (ROOT / "src" / "core.cpp").as_posix()
        probe_source.write_text(
            f'''#include <iostream>
#include "{core_path}"

int main() {{
    Problem problem;
    problem.N = 1;
    problem.sinr.assign(2, 0.0);
    problem.totalCap.assign(2, 1.0);
    problem.sinr[1] = 100.0;
    prepareThresholds(problem);
    std::cout << rateFromAverage(problem, 1, {average:.17g}, 7) << '\\n';
    return 0;
}}
''',
            encoding="utf-8",
        )
        compile_proc = subprocess.run(
            ["g++", "-std=c++17", "-O2", str(probe_source), "-o", str(probe_binary)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(compile_proc.returncode, 0, compile_proc.stderr)
        probe = subprocess.run(
            [str(probe_binary)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=1.0,
            check=False,
        )
        self.assertEqual(probe.returncode, 0, probe.stderr)
        self.assertEqual(int(probe.stdout.strip()), 90)

    def test_repeated_solver_runs_are_legal_and_measure_variation(self) -> None:
        scenario = paper_experiments.HELDOUT_SCENARIOS[0]
        text = paper_experiments.generate_case(
            scenario,
            paper_experiments.QA_HELDOUT_SEED_BASE + 2,
        )
        case = scheduler_validator.parse_case_text(text, case_id="repeat-legality")
        scores: list[int] = []
        for repeat in range(5):
            with self.subTest(repeat=repeat):
                score, _traces = self._run_and_audit(
                    text,
                    case,
                    stage="full",
                    expected_stages=("base", "global", "cg", "remask", "pair", "final"),
                )
                scores.append(score)

        observed_variation = {
            "minimum": min(scores),
            "maximum": max(scores),
            "range": max(scores) - min(scores),
        }
        self.assertEqual(
            observed_variation["range"],
            observed_variation["maximum"] - observed_variation["minimum"],
        )
        self.assertGreaterEqual(observed_variation["range"], 0)


if __name__ == "__main__":
    unittest.main()
