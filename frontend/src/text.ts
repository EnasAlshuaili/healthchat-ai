/** Length in characters (code points), matching Python's len() on the server. */
export function charCount(text: string): number {
  return [...text].length;
}
