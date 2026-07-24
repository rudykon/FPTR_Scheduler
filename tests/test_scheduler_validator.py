from __future__ import annotations

import math
import unittest
from collections.abc import Sequence

from tools import scheduler_validator


def _counted(values: Sequence[int]) -> str:
    return " ".join([str(len(values)), *(str(value) for value in values)])


def make_case_text(
    *,
    caps: Sequence[Sequence[float]],
    buffers: Sequence[int],
    sinrs: Sequence[float],
    sub_resources: Sequence[Sequence[int]],
    resource_count: int,
    beam_max: int = 2,
    groups: Sequence[Sequence[int]] = (),
    su: Sequence[int] = (),
) -> str:
    user_count = len(caps)
    beam_count = len(caps[0])
    band_count = len(sub_resources)
    if len(buffers) != user_count or len(sinrs) != user_count:
        raise AssertionError("user data dimensions differ")
    if any(len(row) != beam_count for row in caps):
        raise AssertionError("capability rows have different lengths")

    lines = [
        f"{beam_count} {user_count} {resource_count} {band_count} {beam_max}",
        str(len(groups)),
    ]
    lines.extend(_counted(group) for group in groups)
    lines.append(_counted(su))
    lines.extend(" ".join(str(value) for value in row) for row in caps)
    lines.extend(f"{buffer_value} {sinr_value}" for buffer_value, sinr_value in zip(buffers, sinrs))
    lines.extend(_counted(resources) for resources in sub_resources)
    return "\n".join(lines) + "\n"


def make_output(
    case: scheduler_validator.CaseInput,
    *,
    beams: Sequence[Sequence[int]],
    user_resources: Sequence[Sequence[int]],
) -> str:
    if len(beams) != case.T or len(user_resources) != case.N:
        raise AssertionError("output dimensions differ from case")
    lines = [_counted(ids) for ids in beams]
    lines.extend(_counted(ids) for ids in user_resources)
    return "\n".join(lines) + "\n"


def basic_case() -> scheduler_validator.CaseInput:
    return scheduler_validator.parse_case_text(
        make_case_text(
            caps=((1.0, 1.0),) * 3,
            buffers=(1000, 1000, 1000),
            sinrs=(100.0, 100.0, 100.0),
            sub_resources=((1, 2),),
            resource_count=2,
            groups=((1, 2),),
        ),
        case_id="basic",
    )


class RateContractTests(unittest.TestCase):
    def test_nonadjacent_two_band_resource_uses_exact_memberships(self) -> None:
        case = scheduler_validator.parse_case_text(
            make_case_text(
                caps=((1.0, 99.0),),
                buffers=(1000,),
                sinrs=(21.0,),
                sub_resources=((1,), (2,), (1,)),
                resource_count=2,
                beam_max=3,
            ),
            case_id="nonadjacent",
        )
        self.assertEqual(case.res_bands[1], (1, 3))

        output = make_output(
            case,
            beams=((1,), (2,), (1,)),
            user_resources=((1,),),
        )
        # Only bands 1 and 3 contribute to the numerator, while the confirmed
        # normalization denominator is t2-t1+1 = 3. Thus the selected average
        # is (1 + 1) / 3, yielding rate 8. Dividing by the two memberships
        # instead would incorrectly yield rate 24 for this boundary case.
        self.assertEqual(scheduler_validator.validate_and_score(case, output).transmitted, 8)

    def test_link_adaptation_thresholds_are_right_closed(self) -> None:
        exact = (
            (-10.0, 0, 8),
            (0.0, 8, 24),
            (3.0, 24, 90),
            (10.0, 90, 120),
            (15.0, 120, 162),
            (20.0, 162, 222),
        )
        for threshold, at_threshold, immediately_above in exact:
            with self.subTest(threshold=threshold):
                self.assertEqual(scheduler_validator.cap_of(threshold), at_threshold)
                self.assertEqual(
                    scheduler_validator.cap_of(math.nextafter(threshold, math.inf)),
                    immediately_above,
                )

    def test_sinr_minus_30_and_100_are_accepted_and_scored(self) -> None:
        case = scheduler_validator.parse_case_text(
            make_case_text(
                caps=((1.0,), (1.0,)),
                buffers=(1000, 1000),
                sinrs=(-30.0, 100.0),
                sub_resources=((1, 2),),
                resource_count=2,
            ),
            case_id="sinr-bounds",
        )
        output = make_output(
            case,
            beams=((1,),),
            user_resources=((1,), (2,)),
        )
        self.assertEqual(scheduler_validator.validate_and_score(case, output).transmitted, 222)

    def test_sinr_outside_closed_range_is_rejected(self) -> None:
        for invalid_sinr in (math.nextafter(-30.0, -math.inf), math.nextafter(100.0, math.inf)):
            with self.subTest(sinr=invalid_sinr):
                text = make_case_text(
                    caps=((1.0,),),
                    buffers=(1000,),
                    sinrs=(invalid_sinr,),
                    sub_resources=((1, 2),),
                    resource_count=2,
                )
                with self.assertRaisesRegex(ValueError, r"outside \[-30,100\]"):
                    scheduler_validator.parse_case_text(text)


class SharingContractTests(unittest.TestCase):
    def test_uncovered_and_grouped_users_may_both_be_singletons(self) -> None:
        case = basic_case()
        self.assertEqual(case.ru_id[3], -1)
        self.assertNotIn(3, case.su)
        output = make_output(
            case,
            beams=((1,),),
            user_resources=((1,), (), (2,)),
        )
        result = scheduler_validator.validate_and_score(case, output)
        self.assertEqual(result.transmitted, 444)

    def test_uncovered_user_cannot_join_a_multi_user_share(self) -> None:
        case = basic_case()
        output = make_output(
            case,
            beams=((1,),),
            user_resources=((1,), (), (1,)),
        )
        with self.assertRaisesRegex(ValueError, "same compatibility group"):
            scheduler_validator.validate_and_score(case, output)

    def test_m16_and_twenty_user_compatibility_group_are_legal(self) -> None:
        groups: list[tuple[int, ...]] = [tuple(range(1, 21))]
        groups.extend((user, user + 1) for user in range(21, 51, 2))
        self.assertEqual(len(groups), 16)

        case = scheduler_validator.parse_case_text(
            make_case_text(
                caps=((1.0,),) * 50,
                buffers=(1000,) * 50,
                sinrs=(100.0,) * 50,
                sub_resources=((1, 2),),
                resource_count=2,
                groups=groups,
            ),
            case_id="max-groups",
        )
        self.assertEqual(len(case.ru), 16)
        self.assertEqual(len(case.ru[0]), 20)

        output = make_output(
            case,
            beams=((1,),),
            user_resources=tuple((1,) if user <= 20 else () for user in range(1, 51)),
        )
        result = scheduler_validator.validate_and_score(case, output)
        self.assertEqual(result.transmitted, 20 * 222)


class OutputValidationTests(unittest.TestCase):
    def test_total_beam_budget_is_enforced_across_subbands(self) -> None:
        case = scheduler_validator.parse_case_text(
            make_case_text(
                caps=((1.0, 1.0),),
                buffers=(1000,),
                sinrs=(100.0,),
                sub_resources=((1,), (2,)),
                resource_count=2,
                beam_max=2,
            )
        )
        output = make_output(
            case,
            beams=((1, 2), (1,)),
            user_resources=((),),
        )
        with self.assertRaisesRegex(ValueError, "beam budget 3 > 2"):
            scheduler_validator.validate_and_score(case, output)

    def test_allocated_resource_requires_beams_on_each_exact_membership(self) -> None:
        case = scheduler_validator.parse_case_text(
            make_case_text(
                caps=((1.0,),),
                buffers=(1000,),
                sinrs=(100.0,),
                sub_resources=((1,), (2,), (1,)),
                resource_count=2,
            )
        )
        output = make_output(
            case,
            beams=((1,), (1,), ()),
            user_resources=((1,),),
        )
        with self.assertRaisesRegex(ValueError, "related subband 3 has an empty beam set"):
            scheduler_validator.validate_and_score(case, output)

    def test_duplicate_resource_on_user_row_is_rejected(self) -> None:
        case = basic_case()
        output = make_output(
            case,
            beams=((1,),),
            user_resources=((1, 1), (), ()),
        )
        with self.assertRaisesRegex(ValueError, "duplicate resource id"):
            scheduler_validator.validate_and_score(case, output)

    def test_repeated_validation_remains_legal_and_deterministic(self) -> None:
        case = basic_case()
        output = make_output(
            case,
            beams=((1,),),
            user_resources=((1,), (1,), (2,)),
        )
        scores = [scheduler_validator.validate_and_score(case, output).transmitted for _ in range(50)]
        self.assertEqual(scores, [scores[0]] * 50)
        self.assertGreater(scores[0], 0)


class AdditionalContractTests(unittest.TestCase):
    def test_zero_or_three_resource_memberships_are_rejected(self) -> None:
        zero_membership = make_case_text(
            caps=((1.0,),),
            buffers=(1,),
            sinrs=(0.0,),
            sub_resources=((1,),),
            resource_count=2,
        )
        with self.assertRaisesRegex(ValueError, "do not cover resource 2"):
            scheduler_validator.parse_case_text(zero_membership)

        three_memberships = make_case_text(
            caps=((1.0,),),
            buffers=(1,),
            sinrs=(0.0,),
            sub_resources=((1, 2), (1,), (1,)),
            resource_count=2,
        )
        with self.assertRaisesRegex(ValueError, "one or two subbands"):
            scheduler_validator.parse_case_text(three_memberships)

    def test_su_metadata_allows_singletons_but_not_sharing(self) -> None:
        case = scheduler_validator.parse_case_text(
            make_case_text(
                caps=((1.0,), (1.0,)),
                buffers=(1000, 1000),
                sinrs=(100.0, 100.0),
                sub_resources=((1, 2),),
                resource_count=2,
                su=(1, 2),
            )
        )
        singleton = make_output(case, beams=((1,),), user_resources=((1,), (2,)))
        self.assertEqual(scheduler_validator.validate_and_score(case, singleton).transmitted, 444)
        shared = make_output(case, beams=((1,),), user_resources=((1,), (1,)))
        with self.assertRaisesRegex(ValueError, "same compatibility group"):
            scheduler_validator.validate_and_score(case, shared)

    def test_legacy_user_rows_with_subband_ids_are_rejected(self) -> None:
        case = basic_case()
        lines = [_counted((1,)), "1 1 1", "0", "0"]
        with self.assertRaisesRegex(ValueError, "declared count 1 but found 2 ids"):
            scheduler_validator.validate_and_score(case, "\n".join(lines) + "\n")

    def test_maximum_dimensions_accept_a_legal_empty_fallback(self) -> None:
        groups = [tuple(range(1, 21))]
        groups.extend((user, user + 1) for user in range(21, 51, 2))
        sub_resources = [[] for _ in range(18)]
        for resource in range(1, 73):
            sub_resources[(resource - 1) % 18].append(resource)
        case = scheduler_validator.parse_case_text(
            make_case_text(
                caps=((1.0,) * 32,) * 100,
                buffers=(1,) * 100,
                sinrs=tuple(-30.0 if user % 2 else 100.0 for user in range(100)),
                sub_resources=tuple(tuple(items) for items in sub_resources),
                resource_count=72,
                beam_max=255,
                groups=tuple(groups),
                su=tuple(range(51, 80)),
            ),
            case_id="max-boundary",
        )
        output = make_output(
            case,
            beams=tuple(() for _ in range(case.T)),
            user_resources=tuple(() for _ in range(case.N)),
        )
        result = scheduler_validator.validate_and_score(case, output)
        self.assertEqual((case.P, case.N, case.K, len(case.ru), len(case.ru[0]), len(case.su)),
                         (32, 100, 72, 16, 20, 29))
        self.assertEqual(result.transmitted, 0)


if __name__ == "__main__":
    unittest.main()
