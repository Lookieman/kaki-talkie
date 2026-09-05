// v1.0 | 04-Sep-2026 | Define and validate the WP1.3 device-state flow.

export const DEVICE_STATES = [
  "idle",
  "listening",
  "thinking",
  "speaking",
  "printing",
] as const;

export type DeviceState = (typeof DEVICE_STATES)[number];

const ALLOWED_TRANSITIONS: Record<DeviceState, readonly DeviceState[]> = {
  idle: ["listening"],
  listening: ["thinking", "idle"],
  thinking: ["speaking", "idle"],
  speaking: ["printing", "idle"],
  printing: ["idle"],
};

export function canTransition(from: DeviceState, to: DeviceState): boolean {
  return ALLOWED_TRANSITIONS[from].includes(to);
}
