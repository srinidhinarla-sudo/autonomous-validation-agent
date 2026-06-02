"""
Visual regression tests.

Renders PNG mockups for every infotainment state, compares them against
baseline screenshots, and fails if any image differs by more than a
configurable pixel-percentage threshold.

Baseline generation:
    pytest tests/test_visual_regression.py --generate-baseline

Normal run:
    pytest tests/test_visual_regression.py
"""

import os
from pathlib import Path

import pytest

try:
    import infotainment_sm as sm
    _SM_AVAILABLE = True
except ImportError:
    _SM_AVAILABLE = False

try:
    from PIL import Image  # type: ignore
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

BASELINE_DIR = Path(__file__).parent.parent / "screenshots" / "baseline"
CURRENT_DIR  = Path(__file__).parent.parent / "screenshots" / "current"
DIFF_DIR     = Path(__file__).parent.parent / "screenshots" / "diffs"
PIXEL_DIFF_THRESHOLD = 0.5  # percentage — fail if > 0.5 % pixels differ


def get_generate_baseline(request):
    try:
        return request.config.getoption("--generate-baseline")
    except ValueError:
        return False


pytestmark = [
    pytest.mark.skipif(not _SM_AVAILABLE, reason="infotainment_sm not built"),
    pytest.mark.skipif(not _PIL_AVAILABLE, reason="Pillow not installed"),
]


@pytest.fixture(scope="session")
def all_state_names():
    return [n for n in sm.InfotainmentStateMachine.all_state_names()
            if n != "STATE_COUNT"]


@pytest.fixture(scope="session")
def renderer():
    try:
        from python.state_renderer import render_state, pixel_diff, image_hash
        return render_state, pixel_diff, image_hash
    except ImportError as e:
        pytest.skip(f"state_renderer unavailable: {e}")


class TestVisualRegression:
    def test_baseline_exists_or_generate(self, request, renderer, all_state_names):
        """If no baselines exist, generate them now (first-run bootstrap)."""
        render_state, _, _ = renderer
        BASELINE_DIR.mkdir(parents=True, exist_ok=True)
        generate = get_generate_baseline(request)

        missing = [n for n in all_state_names
                   if not (BASELINE_DIR / f"{n}.png").exists()]

        if missing or generate:
            for name in (missing if not generate else all_state_names):
                state = getattr(sm.State, name)
                render_state(state, BASELINE_DIR / f"{name}.png")
            pytest.skip(f"Generated {len(missing or all_state_names)} baseline screenshots — "
                        "re-run without --generate-baseline to compare.")

    @pytest.mark.parametrize("state_name",
        [n for n in (sm.InfotainmentStateMachine.all_state_names()
                     if _SM_AVAILABLE else [])
         if n != "STATE_COUNT"])
    def test_state_screenshot_matches_baseline(self, request, renderer, state_name):
        render_state, pixel_diff, image_hash = renderer

        baseline_path = BASELINE_DIR / f"{state_name}.png"
        if not baseline_path.exists():
            pytest.skip(f"No baseline for {state_name} — run with --generate-baseline")

        CURRENT_DIR.mkdir(parents=True, exist_ok=True)
        current_path = CURRENT_DIR / f"{state_name}.png"

        state = getattr(sm.State, state_name)
        render_state(state, current_path)

        # Fast path: hash equality
        if image_hash(baseline_path) == image_hash(current_path):
            return

        # Slow path: pixel diff
        diff_count, diff_pct = pixel_diff(baseline_path, current_path)
        if diff_pct > PIXEL_DIFF_THRESHOLD:
            DIFF_DIR.mkdir(parents=True, exist_ok=True)
            _save_diff_image(baseline_path, current_path,
                             DIFF_DIR / f"{state_name}_diff.png")
            pytest.fail(
                f"Visual regression: {state_name} differs by {diff_pct:.2f}% "
                f"({diff_count} pixels). Threshold: {PIXEL_DIFF_THRESHOLD}%. "
                f"Diff saved to screenshots/diffs/{state_name}_diff.png"
            )

    def test_all_states_render_without_error(self, renderer, all_state_names):
        render_state, _, _ = renderer
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            for name in all_state_names:
                state = getattr(sm.State, name)
                p = render_state(state, Path(tmp) / f"{name}.png")
                assert p.exists(), f"Failed to render {name}"
                assert p.stat().st_size > 0, f"Empty PNG for {name}"

    def test_rendered_images_have_correct_dimensions(self, renderer, all_state_names):
        render_state, _, _ = renderer
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            for name in all_state_names[:5]:  # spot-check first 5
                state = getattr(sm.State, name)
                p = render_state(state, Path(tmp) / f"{name}.png")
                img = Image.open(str(p))
                assert img.size == (480, 270), \
                    f"{name}: expected (480,270) got {img.size}"

    def test_different_states_produce_different_images(self, renderer):
        """HOME and ERROR_SCREEN should not look identical."""
        render_state, pixel_diff, _ = renderer
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p_home  = render_state(sm.State.HOME,  Path(tmp) / "HOME.png")
            p_error = render_state(sm.State.ERROR_SCREEN, Path(tmp) / "ERROR.png")
            _, pct = pixel_diff(p_home, p_error)
            assert pct > 0.0, "HOME and ERROR_SCREEN rendered identically!"


def _save_diff_image(base_path: Path, curr_path: Path, out_path: Path) -> None:
    try:
        from PIL import ImageChops, ImageEnhance
        base = Image.open(str(base_path)).convert("RGB")
        curr = Image.open(str(curr_path)).convert("RGB")
        diff = ImageChops.difference(base, curr)
        enhanced = ImageEnhance.Brightness(diff).enhance(5.0)
        enhanced.save(str(out_path))
    except Exception:
        pass  # diff visualisation is best-effort
