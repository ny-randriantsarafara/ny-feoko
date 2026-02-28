export interface DiffSegment {
  readonly text: string;
  readonly type: "equal" | "added" | "removed";
}

/**
 * Simple word-level diff between two strings.
 * Uses a greedy LCS approach suitable for short texts.
 */
export function wordDiff(original: string, modified: string): DiffSegment[] {
  const oldWords = original.split(/(\s+)/);
  const newWords = modified.split(/(\s+)/);

  const oldLen = oldWords.length;
  const newLen = newWords.length;

  const lcs: number[][] = Array.from({ length: oldLen + 1 }, () =>
    Array(newLen + 1).fill(0),
  );

  for (let i = oldLen - 1; i >= 0; i--) {
    for (let j = newLen - 1; j >= 0; j--) {
      if (oldWords[i] === newWords[j]) {
        lcs[i][j] = lcs[i + 1][j + 1] + 1;
      } else {
        lcs[i][j] = Math.max(lcs[i + 1][j], lcs[i][j + 1]);
      }
    }
  }

  const result: DiffSegment[] = [];
  let i = 0;
  let j = 0;

  while (i < oldLen && j < newLen) {
    if (oldWords[i] === newWords[j]) {
      result.push({ text: oldWords[i], type: "equal" });
      i++;
      j++;
    } else if ((lcs[i + 1]?.[j] ?? 0) >= (lcs[i]?.[j + 1] ?? 0)) {
      result.push({ text: oldWords[i], type: "removed" });
      i++;
    } else {
      result.push({ text: newWords[j], type: "added" });
      j++;
    }
  }

  while (i < oldLen) {
    result.push({ text: oldWords[i], type: "removed" });
    i++;
  }
  while (j < newLen) {
    result.push({ text: newWords[j], type: "added" });
    j++;
  }

  return result;
}
