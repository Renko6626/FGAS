export function money(fen: number) {
  const value = BigInt(fen);
  const absolute = value < 0n ? -value : value;
  return `${value < 0n ? "-" : ""}${absolute / 100n}.${(absolute % 100n).toString().padStart(2, "0")}`;
}
export const statuses: Record<string, string> = {
  pending: "待审批",
  posted: "已过账",
  rejected: "已拒绝",
  reversed: "已冲销",
};
