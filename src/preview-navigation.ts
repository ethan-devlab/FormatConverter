/** Accumulate trackpad deltas and accept at most one step per cooldown. */
export class WheelNavigation {
  private delta = 0;
  private lastEvent = -Infinity;
  private lastStep = -Infinity;

  step(deltaY: number, mode: number, now: number): number {
    if (!Number.isFinite(deltaY) || !deltaY) return 0;
    if (now - this.lastStep < 450) return 0;
    const pixels = deltaY * (mode === 1 ? 16 : mode === 2 ? 600 : 1);
    if (now - this.lastEvent > 200 || Math.sign(pixels) !== Math.sign(this.delta)) this.delta = 0;
    this.lastEvent = now;
    this.delta += pixels;
    if (Math.abs(this.delta) < 60) return 0;
    const result = Math.sign(this.delta);
    this.delta = 0;
    this.lastStep = now;
    return result;
  }
}
