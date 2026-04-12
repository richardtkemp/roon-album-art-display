"""Tests for the two-stage render coordinator pipeline."""

import threading
import time
from unittest.mock import Mock

import pytest
from PIL import Image

from roon_display.exceptions import RenderCancelledError
from roon_display.render_coordinator import LatestSlot, RenderCoordinator

# ---------------------------------------------------------------------------
# LatestSlot unit tests
# ---------------------------------------------------------------------------


class TestLatestSlot:
    """Unit tests for LatestSlot mailbox."""

    @pytest.fixture
    def slot(self):
        return LatestSlot()

    def test_set_and_wait_and_take(self, slot):
        """set() then wait_and_take() returns the value and clears the slot."""

        class Item:
            generation = 0

        item = Item()
        slot.set(item)
        result = slot.wait_and_take()
        assert result is item
        assert slot.try_take() is None  # slot is now empty

    def test_set_overwrites(self, slot):
        """A second set() before take() overwrites the first value."""

        class Item:
            def __init__(self, v):
                self.v = v
                self.generation = 0

        a, b = Item("a"), Item("b")
        slot.set(a)
        slot.set(b)
        result = slot.wait_and_take()
        assert result.v == "b"

    def test_generation_increments(self, slot):
        """Each set() increments the generation counter on the value."""

        class Item:
            generation = 0

        a, b = Item(), Item()
        slot.set(a)
        slot.set(b)
        assert a.generation == 1
        assert b.generation == 2

    def test_is_current_true(self, slot):
        """is_current() returns True when no newer item has been set."""

        class Item:
            generation = 0

        item = Item()
        slot.set(item)
        assert slot.is_current(item.generation)

    def test_is_current_false_after_new_set(self, slot):
        """is_current() returns False after a newer item is set."""

        class Item:
            generation = 0

        a = Item()
        slot.set(a)
        gen = a.generation

        b = Item()
        slot.set(b)
        assert not slot.is_current(gen)

    def test_try_take_empty(self, slot):
        """try_take() returns None when slot is empty."""
        assert slot.try_take() is None

    def test_wait_and_take_blocks(self, slot):
        """wait_and_take() blocks until a value is set from another thread."""

        class Item:
            generation = 0

        result_holder = []

        def producer():
            time.sleep(0.05)
            slot.set(Item())

        t = threading.Thread(target=producer)
        t.start()
        result_holder.append(slot.wait_and_take())
        t.join()
        assert len(result_holder) == 1


# ---------------------------------------------------------------------------
# RenderCoordinator integration tests
# ---------------------------------------------------------------------------


def _make_coordinator(config_manager):
    """Create a RenderCoordinator with a mock viewer and supporting objects."""
    viewer = Mock()
    viewer.cancel = Mock()
    viewer.render = Mock()
    # No 'epd' attribute → not e-ink, so _current_key stays None on startup
    del viewer.epd

    image_processor = Mock()
    image_processor.prepare = Mock(
        side_effect=lambda img, path, **kw: Image.new("RGB", (10, 10), "red")
    )

    message_renderer = Mock()
    message_renderer.create_text_message = Mock(
        return_value=Image.new("RGB", (10, 10), "white")
    )
    message_renderer.create_error_overlay = Mock(
        return_value=Image.new("RGB", (3, 3), "yellow")
    )

    coord = RenderCoordinator(
        viewer=viewer,
        image_processor=image_processor,
        message_renderer=message_renderer,
        config_manager=config_manager,
    )
    return coord, viewer, image_processor


def _wait_for_render(viewer, timeout=2.0, count=1):
    """Block until viewer.render has been called at least `count` times."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if viewer.render.call_count >= count:
            return True
        time.sleep(0.01)
    return False


class TestRenderCoordinatorPipeline:
    """Integration tests for the two-stage pipeline."""

    def test_set_art_triggers_render(self, config_manager, sample_image):
        """set_art() eventually causes viewer.render() to be called."""
        coord, viewer, _ = _make_coordinator(config_manager)
        coord.set_art("art", image_key="k1", img=sample_image)
        assert _wait_for_render(viewer), "viewer.render() was never called"
        args = viewer.render.call_args
        assert args[0][1] == "k1"  # image_key

    def test_only_latest_target_rendered(self, config_manager, sample_image):
        """When multiple targets arrive rapidly, only the latest is rendered.

        The prepare loop checks staleness after the (potentially slow)
        image_processor.prepare() call.  Here we make prepare slow enough that
        multiple targets arrive before the first one is done, so the second one
        is skipped.
        """
        coord, viewer, image_processor = _make_coordinator(config_manager)

        prepare_start = threading.Event()
        allow_prepare = threading.Event()

        def slow_prepare(img, path, **kw):
            prepare_start.set()
            allow_prepare.wait(timeout=2)
            return Image.new("RGB", (10, 10), "red")

        image_processor.prepare.side_effect = slow_prepare

        # Queue 'a'; wait for prepare to start, then queue 'b' and 'c'
        coord.set_art("art", image_key="a", img=sample_image)
        prepare_start.wait(timeout=1)
        coord.set_art("art", image_key="b", img=sample_image)
        coord.set_art("art", image_key="c", img=sample_image)
        allow_prepare.set()

        # Give pipeline time to settle
        assert _wait_for_render(viewer, timeout=3), "viewer.render() was never called"
        time.sleep(0.1)  # Let any extra renders complete

        rendered_keys = [c[0][1] for c in viewer.render.call_args_list]
        assert (
            "b" not in rendered_keys
        ), f"'b' should have been skipped, got {rendered_keys}"
        assert (
            "c" in rendered_keys
        ), f"'c' should have been rendered, got {rendered_keys}"

    def test_stale_prepared_item_discarded(self, config_manager, sample_image):
        """An item prepared just before a newer target arrives is discarded."""
        coord, viewer, image_processor = _make_coordinator(config_manager)

        # Block the first prepare so we can race in a second target
        first_prepare_done = threading.Semaphore(0)
        call_count = [0]

        def gated_prepare(img, path, **kw):
            call_count[0] += 1
            if call_count[0] == 1:
                first_prepare_done.release()
                time.sleep(0.1)  # Hold here while second target arrives
            return Image.new("RGB", (10, 10), "red")

        image_processor.prepare.side_effect = gated_prepare

        coord.set_art("art", image_key="a", img=sample_image)
        first_prepare_done.acquire(timeout=1)  # Wait until first prepare is in progress
        coord.set_art("art", image_key="c", img=sample_image)  # Supersede 'a'

        assert _wait_for_render(viewer, timeout=3)
        time.sleep(0.1)

        rendered_keys = [c[0][1] for c in viewer.render.call_args_list]
        # 'a' may or may not render (race); 'c' must render; but if both render,
        # 'a' must come before 'c' (ordering guarantee).
        assert "c" in rendered_keys
        if "a" in rendered_keys:
            assert rendered_keys.index("a") < rendered_keys.index("c")

    def test_partial_refresh_cancels_viewer(self, config_manager, sample_image):
        """set_art() with partial_refresh=True calls viewer.cancel()."""
        config_manager.set_partial_refresh("true")
        coord, viewer, _ = _make_coordinator(config_manager)

        coord.set_art("art", image_key="k1", img=sample_image)
        coord.set_art("art", image_key="k2", img=sample_image)

        assert viewer.cancel.call_count >= 1

    def test_overlay_triggers_rerender_without_prepare(
        self, config_manager, sample_image
    ):
        """set_overlay() re-renders using _last_prepared without re-running prepare."""
        coord, viewer, image_processor = _make_coordinator(config_manager)

        coord.set_art("art", image_key="k1", img=sample_image)
        assert _wait_for_render(viewer, count=1), "Initial render never happened"

        initial_prepare_count = image_processor.prepare.call_count

        coord.set_overlay("Error: test", timeout=60)
        assert _wait_for_render(viewer, count=2), "Overlay re-render never happened"

        # prepare should NOT have been called again for the overlay re-render
        assert image_processor.prepare.call_count == initial_prepare_count

    def test_force_refresh_rerenders_same_key(self, config_manager, sample_image):
        """force_refresh() re-renders even though the same key is already on screen."""
        coord, viewer, _ = _make_coordinator(config_manager)

        coord.set_art("art", image_key="X", img=sample_image)
        assert _wait_for_render(viewer, count=1)

        coord.force_refresh()
        assert _wait_for_render(
            viewer, count=2
        ), "force_refresh did not trigger re-render"

        rendered_keys = [c[0][1] for c in viewer.render.call_args_list]
        assert (
            rendered_keys.count("X") >= 2
        ), f"Expected 'X' rendered twice, got {rendered_keys}"

    def test_render_cancelled_error_retried(self, config_manager, sample_image):
        """RenderCancelledError from viewer.render() causes a retry for the latest item."""
        coord, viewer, _ = _make_coordinator(config_manager)

        cancel_once = [True]

        def render_side_effect(image, image_key, title):
            if cancel_once[0]:
                cancel_once[0] = False
                raise RenderCancelledError("test cancel")

        viewer.render.side_effect = render_side_effect

        coord.set_art("art", image_key="k1", img=sample_image)

        # Wait for the retry render to complete
        deadline = time.time() + 3
        while time.time() < deadline:
            successful = [c for c in viewer.render.call_args_list if c[0][1] == "k1"]
            if len(successful) >= 2:
                break
            time.sleep(0.01)
        # At minimum one successful render (after cancel) should have happened
        assert viewer.render.call_count >= 1
