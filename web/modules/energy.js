/**
 * energy.js — Energy Level 計算 + CLIMAX判定
 */

import { playSE } from "./se-player.js";

let energyScore = 0;
let energyLevel = 0; // 0=low, 1=mid, 2=high
let lastEnergyUpdate = 0;
const ENERGY_THRESHOLDS = [3, 8];

export function updateEnergy(cueTypes, cueLabels) {
  const now = Date.now();
  const dt = lastEnergyUpdate ? (now - lastEnergyUpdate) / 1000 : 0;
  lastEnergyUpdate = now;

  energyScore *= Math.pow(0.5, dt / 2);

  for (let i = 0; i < cueTypes.length; i++) {
    const type = cueTypes[i];
    const label = cueLabels[i] || "";
    if (type === "STRUM") {
      if (label.includes("HEAVY")) energyScore += 3;
      else if (label.includes("MEDIUM")) energyScore += 2;
      else energyScore += 1;
    } else if (type === "JUMP") {
      energyScore += 5;
    }
  }

  const prevLevel = energyLevel;
  if (energyScore >= ENERGY_THRESHOLDS[1]) energyLevel = 2;
  else if (energyScore >= ENERGY_THRESHOLDS[0]) energyLevel = 1;
  else energyLevel = 0;

  if (energyLevel > prevLevel) playSE("energy_up", 0.5);
  if (energyLevel < prevLevel) playSE("energy_down", 0.5);
}

export function getEnergyLevel() {
  return energyLevel;
}
