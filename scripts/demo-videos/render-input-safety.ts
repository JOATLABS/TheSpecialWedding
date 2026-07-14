import fs from 'node:fs';
import path from 'node:path';

function collectFiles(directory: string): string[] {
  if (!fs.existsSync(directory)) return [];

  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const absolutePath = path.join(directory, entry.name);
    if (entry.isDirectory()) return collectFiles(absolutePath);
    return [absolutePath];
  });
}

export function findUnexpectedPublicRenderInputs(rootDir: string): string[] {
  const stagingDirectory = path.join(
    rootDir,
    'public',
    'demo-videos',
    '.render-input',
  );

  return collectFiles(stagingDirectory)
    .map((filePath) => path.relative(rootDir, filePath).split(path.sep).join('/'))
    .sort();
}
