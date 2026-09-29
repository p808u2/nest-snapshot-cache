# Idea: keep a last-good Nest snapshot available for HomeKit

I have two Nest doorbells connected to Apple Home through Scrypted's Google Device Access plugin. Live view works well, but HomeKit sometimes opens with an old image or briefly says `Snapshot Failed` while a new Nest stream is starting.

I put together a small local snapshot service alongside Scrypted to see if this could be improved. It keeps one known-good JPEG per camera and returns that immediately while it obtains a newer frame in the background.

The service currently does the following:

- Produces a 1280x720 image, which fits HomeKit's 16:9 layout nicely.
- Applies a slightly different crop for each doorbell.
- Adds a small timestamp in 24-hour format so it is obvious how old the image is.
- Rejects frames that look corrupted, smeared, or affected by banding.
- Replaces the cached file atomically, so a request never sees a half-written JPEG.
- Returns the cached image immediately, then refreshes it if it is more than about 30 seconds old.
- Refreshes hourly, shortly after sunrise and sunset, and after motion or a doorbell press when available.
- Runs as a persistent background service on the Mac.

In practice, this made HomeKit feel much better. It always had a usable image to show, and then replaced it a few seconds later when the Nest stream produced a fresh frame. I no longer saw the blank tile/`Snapshot Failed` behavior during normal use.

I wonder if something similar could be built into the Google Device Access plugin itself: keep a persistent last-good event snapshot, expose it through Scrypted's normal camera snapshot path, and do a short background refresh after serving the cached image.

This seems like it could remain platform-independent. The plugin already knows about the camera events and snapshot requests; the missing piece may just be persistent caching, validation, and a refresh policy.

This is based on a working two-camera prototype rather than a request to change Nest's event system. The main problem appears to be snapshot acquisition latency and cache behavior, not live-stream reliability.

I have intentionally left out credentials, device IDs, local addresses, and private camera URLs.
