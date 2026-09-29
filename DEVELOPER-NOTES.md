# Proposal: stale-while-refresh snapshots for cloud cameras

## The problem

Some cloud cameras and doorbells provide a good live stream but are poor
snapshot sources. Starting the cloud stream for every HomeKit thumbnail request
can take several seconds or time out. Apple Home may ask for visible camera
thumbnails repeatedly, often around ten seconds apart, so synchronous capture
can produce `Snapshot Failed`, slow HomeKit handlers, or effectively continuous
cloud streaming.

## Prototype behavior

This prototype places a small stale-while-refresh layer behind Scrypted's
Snapshot URL setting:

1. Always return the last known-good JPEG immediately.
2. If that JPEG is at least 30 seconds old, begin one background capture after
   returning it.
3. Serialize refreshes so concurrent requests never start duplicate streams.
4. Close the on-demand RTSP stream after capturing one frame.
5. Stop age-based refreshes automatically when thumbnail requests stop.
6. Force an additional refresh 30 seconds after motion or a doorbell press so
   the cached image reflects the useful aftermath of the event.
7. Capture both cameras hourly and 15 minutes after local sunrise and sunset,
   so a Home tile begins with a reasonably current image even after hours away.
8. Preserve the previous JPEG whenever capture or post-processing fails.

The result is an immediate, useful Home tile even when the cloud stream is slow.
On the next Home polling cycle, the tile receives the newly captured frame.

## Presentation details

- Normalize snapshots to an actual 16:9 frame (1280x720 here) using
  aspect-preserving scale-and-crop rather than stretching.
- Allow a per-camera crop bias. Portrait doorbells often benefit from a lower
  crop that retains the walkway or package area; 4:3 cameras may prefer center.
- Optionally burn in a restrained capture label such as
  `Snapshot · 2026-09-07 08:45:10`. The prototype uses local frame receipt
  time, not an authoritative camera exposure time. This makes a stale image explicit while Home's own
  elapsed-time label continues to show how recently Home received it.
- Write new JPEGs atomically and validate them before replacing the cache.
- Home's mosaic may crop the sides of a thumbnail. Our final layout places
  the label at top center with 28 pixels of top padding: a 32-point date/Snapshot
  heading above a 54-point clock, on a translucent rounded background. The
  two-line layout keeps the label narrow enough for the observed cropped tiles.
- Decode and check both the captured and rendered image for repeated textured
  rows characteristic of vertical smearing. Preserve the previous cache on
  rejection and expose rejection diagnostics. This is a conservative heuristic,
  not a guarantee against every form of image corruption.

## Possible Scrypted feature

A reusable Snapshot plugin mode could expose this as **Stale While Refresh** or
**Cloud Camera Snapshot Cache**, with settings such as:

- Maximum snapshot age while actively requested
- Minimum retry/cooldown interval
- Initial request wait when no cache exists
- Event-triggered delayed refresh
- Output aspect ratio and dimensions
- Horizontal/vertical crop focus
- Optional capture timestamp overlay
- Retain last good snapshot on failure

Useful diagnostics would include cache age, capture duration, last error,
request interval, refresh reason (`request`, `motion`, `doorbell`, or manual),
and whether a capture is currently running.

## Important distinction

The consumer's polling interval and the source-camera refresh interval should
remain separate. Home can request a JPEG every ten seconds and still receive an
instant response, while the plugin refreshes the cloud camera only every 30
seconds—and only while requests continue. Matching every Home request with a
new cloud stream would lose the latency and reliability benefits.

## Current prototype scope

- Two wired Google Nest doorbells exposed to Apple Home through Scrypted
- Scrypted and the cache service run on an M4 Mac mini
- No continuous Scrypted prebuffer
- No Raspberry Pi involvement
- Localhost-only snapshot and health endpoints

This is a working proof of concept rather than a general-purpose plugin. A
production implementation should use Scrypted's device/event APIs directly,
avoid platform-specific timestamp rendering, bound all diagnostic history, and
make privacy-sensitive request logging opt-in.
