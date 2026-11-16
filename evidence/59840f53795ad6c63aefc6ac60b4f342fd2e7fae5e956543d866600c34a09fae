# Plan: Capybara mode

Add `caffe --capybara` to replace the resident cat with a capybara riding a
turtle. The pair moves at half the cat's speed, and pressing `f` feeds it
lettuce instead of fish. Running `caffe` without the flag stays unchanged.

## Approach

1. Extend `check_args()` to accept `--capybara` and pass the selection through
   `main()` into an optional mode on the existing `Cat` controller. Preserve
   help, update, invalid-argument handling and the interactive-terminal check.
   Keep the default constructor compatible with existing callers; visiting
   cats remain cats. Give the resident's title an appropriate description.
2. Add a procedurally drawn capybara-on-turtle sprite using the existing drawing
   primitives and `SPRITES`/`Gallery` pipeline. Keep its footprint at seven
   columns by three rows, with mirrored and scaled variants. Support every
   pose emitted by `Cat.pose()`, including petting, eating, sleeping, calling
   orders and cup cleanup, with the turtle visible beneath the capybara.
   Select this sprite in `Cat.place()` without changing normal cat sprites.
3. Apply a single half-speed multiplier after the walking speed is selected,
   including chase and errand overrides. Double leap duration in this mode.
   Day/night and rush-hour speed changes must retain the slowdown. Preserve
   distance-based animation, arrival handling and existing order interactions.
4. Add a lettuce treat sprite in the existing two-column, one-row footprint,
   with the same four progressively eaten stages as the fish. Select it for
   capybara feeding and mention lettuce in the successful feed message. Keep
   the feeding duration, three-per-ten-minute limit, pets and receipt counts
   unchanged. Do not otherwise redesign mice, visiting cats or fika behavior.
5. Document the flag, turtle ride, slower movement and lettuce in `README.md`
   and the script's help text. Add focused standard-library `unittest` tests
   in `tests/test_capybara_mode.py`, following the existing `runpy` pattern.

## Scope

- `caffe`
- `README.md`
- `tests/test_capybara_mode.py`

## Tests

- `test_capybara_mode.CapybaraModeTests.test_cli_modes_help_and_invalid_arguments`
- `test_capybara_mode.CapybaraModeTests.test_startup_uses_selected_mode`
- `test_capybara_mode.CapybaraModeTests.test_default_cat_and_visitors_stay_cats`
- `test_capybara_mode.CapybaraModeTests.test_capybara_moves_at_half_speed_in_all_contexts`
- `test_capybara_mode.CapybaraModeTests.test_capybara_leaps_slower_and_lands_on_target`
- `test_capybara_mode.CapybaraModeTests.test_all_capybara_poses_include_rider_and_turtle`
- `test_capybara_mode.CapybaraModeTests.test_feeding_selects_lettuce_and_preserves_limits`
- `test_capybara_mode.CapybaraModeTests.test_lettuce_disappears_progressively_with_bites`
- `test_capybara_mode.CapybaraModeTests.test_capybara_completes_cup_cleanup`
- `test_capybara_mode.CapybaraModeTests.test_rendering_fits_and_text_only_has_no_pictures`

CLI tests cover no arguments, `--capybara`, both help aliases, update dispatch,
invalid arguments and non-interactive rejection without launching system
processes. Mock terminal and macOS services for startup tests and verify that
the selected mode reaches the resident controller. Verify default and visiting
cats still select cat and fish sprites.

Compare actual displacement for equal elapsed time in day, night, rush, chase
and errand contexts, including after repeated `bar_clock()` calls. Check leap
duration and landing separately. Exercise all emitted pose variants, both
directions and existing scales; assert expected dimensions, distinguishable
rider and turtle regions, and exact horizontal mirroring rather than merely
checking for nonempty images. Check lettuce selection, feed text, timing and
rate-limit recovery; lettuce's opaque area must decrease through all bite
stages.

Render a finished order through cleanup and the return to the table to prove
the slower resident does not strand cups. Cover narrow and normal panes and
graphics-disabled rendering. Manually inspect the pair and lettuce in a
kitty-compatible terminal, including walking, feeding and sleeping.

Run `python3 -m unittest discover -s tests -v`, `python3 -m py_compile caffe`,
and the repository's Ruff lint and format checks. Existing tests must continue
to pass without changing their expectations.
