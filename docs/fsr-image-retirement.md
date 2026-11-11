# Native FSR image retirement

Native FSR upscaling, interpolation and shared input preparation keep resources from an earlier size
until the GPU finishes their recorded uses. CPU present age cannot establish GPU
completion: GPU waits are optional, a stopped logical queue can resume after its
old submission value has completed, and post-present interpolation is submitted
without signalling the game's present value.

Retirement captures a future value on the global submission timeline, strictly
after the last signal issued during replay. The next signal is recorded after
the old uses: serial recordings, joined parallel segments and held batches all
reach the same Vulkan queue. Completion is queried independently of CPU frames.
An unavailable timeline or exhausted counter yields an invalid zero ticket;
those bundles remain owned rather than being destroyed on an unproven value.
This does not add a GPU wait or change the existing pacing policy.

The internal FSR output is copied into the game's image (upscaling) or an OutSet
image (interpolation) before handoff. The display worker uses the latter, not the
FSR internal images. Its separate drain/idle policy remains unchanged. This fix
also does not address FSR uniform-buffer reuse, external SDK context ownership,
other renderer allocations or device recovery. Input preparation also retains cached
depth views by submission completion when the texture generation changes.

`tests/test_fsr_input_retirement.py` executes the input preparation retirement
functions with delayed completion, immediate completion, out-of-order tickets and
an unavailable timeline. The old four-CPU-frame policy fails the delayed case.

`tests/test_fsr_image_retirement.py` compiles the actual image ownership functions
from both backends, the retirement/progress helpers, and the recording submission,
batch flush and finish functions. A delayed queue model runs commands and signals
in order, independently of CPU presents. It verifies complete view/image ownership,
exact completion, resumed logical submissions, unsignalled post-present work,
queued segments, batches, multiple bundles and unavailable/overflow watermarks.
Queue-segment cases model the worker submission order; they do not execute the
parallel worker scheduler. These CPU tests do not claim a physical GPU fault or
campaign coverage. Native smoke complements, rather than replaces, this proof.
