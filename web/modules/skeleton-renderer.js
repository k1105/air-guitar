/**
 * skeleton-renderer.js — Canvas上にCOCO 17点骨格を描画
 */

const SKELETON_EDGES = [
  [0, 1], [0, 2], [1, 3], [2, 4],
  [5, 6],
  [5, 7], [7, 9],
  [6, 8], [8, 10],
  [5, 11], [6, 12],
  [11, 12],
  [11, 13], [13, 15],
  [12, 14], [14, 16],
];

const SRC_W = 1280;
const SRC_H = 720;

export function drawSkeleton(ctx, kps) {
  const w = ctx.canvas.width;
  const h = ctx.canvas.height;
  const scaleX = w / SRC_W;
  const scaleY = h / SRC_H;

  ctx.strokeStyle = "rgba(0, 200, 255, 0.6)";
  ctx.lineWidth = 2;
  for (const [a, b] of SKELETON_EDGES) {
    const pa = kps[a];
    const pb = kps[b];
    if (pa[2] > 0.3 && pb[2] > 0.3) {
      ctx.beginPath();
      ctx.moveTo(pa[0] * scaleX, pa[1] * scaleY);
      ctx.lineTo(pb[0] * scaleX, pb[1] * scaleY);
      ctx.stroke();
    }
  }

  for (const kp of kps) {
    if (kp[2] > 0.3) {
      ctx.beginPath();
      ctx.arc(kp[0] * scaleX, kp[1] * scaleY, 4, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(0, 200, 255, 0.9)";
      ctx.fill();
    }
  }
}
