#!/usr/bin/env node

/**
 * Release script for the Hausfunk Home Assistant integration.
 * Usage:
 *   npm run release -- patch      (e.g., 0.1.0 -> 0.1.1)
 *   npm run release -- minor      (e.g., 0.1.0 -> 0.2.0)
 *   npm run release -- major      (e.g., 0.1.0 -> 1.0.0)
 *   npm run release -- 0.1.0      (explicit version)
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const MANIFEST_PATH = path.join(__dirname, '..', 'custom_components', 'hausfunk', 'manifest.json');
const ZIP_NAME = 'hausfunk.zip';

function run(cmd) {
  console.log(`\x1b[36m> ${cmd}\x1b[0m`);
  execSync(cmd, { stdio: 'inherit', cwd: path.join(__dirname, '..') });
}

function getNextVersion(currentVersion, bumpType) {
  const parts = currentVersion.split('.').map(Number);
  if (parts.length !== 3) {
    throw new Error(`Invalid current version format: ${currentVersion}`);
  }

  if (bumpType === 'patch') {
    parts[2] += 1;
    return parts.join('.');
  } else if (bumpType === 'minor') {
    parts[1] += 1;
    parts[2] = 0;
    return parts.join('.');
  } else if (bumpType === 'major') {
    parts[0] += 1;
    parts[1] = 0;
    parts[2] = 0;
    return parts.join('.');
  } else if (/^\d+\.\d+\.\d+$/.test(bumpType)) {
    return bumpType;
  } else {
    throw new Error(`Unknown bump type or version format: "${bumpType}". Use patch, minor, major, or X.Y.Z`);
  }
}

function main() {
  const arg = process.argv[2] || 'patch';

  // 1. Run unit tests
  console.log('\x1b[32m[1/6] Running Python unit tests...\x1b[0m');
  run('python3 -m unittest discover -s tests');

  // 2. Read current version and calculate next version
  const manifest = JSON.parse(fs.readFileSync(MANIFEST_PATH, 'utf8'));
  const currentVersion = manifest.version;
  const newVersion = getNextVersion(currentVersion, arg);
  console.log(`\x1b[32m[2/6] Bumping version from ${currentVersion} -> ${newVersion}\x1b[0m`);

  manifest.version = newVersion;
  fs.writeFileSync(MANIFEST_PATH, JSON.stringify(manifest, null, 2) + '\n');

  // 3. Create zip archive
  console.log('\x1b[32m[3/6] Packaging integration zip archive...\x1b[0m');
  run(`zip -r ${ZIP_NAME} custom_components/hausfunk`);

  // 4. Git commit and tag
  console.log('\x1b[32m[4/6] Committing changes and creating git tag...\x1b[0m');
  run(`git add .`);
  run(`git commit -m "release: v${newVersion}"`);
  run(`git tag -a v${newVersion} -m "Release v${newVersion}"`);

  // 5. Git push
  console.log('\x1b[32m[5/6] Pushing commits and tags to GitHub...\x1b[0m');
  run(`git push origin main`);
  run(`git push origin v${newVersion}`);

  // 6. Create GitHub Release with zip asset
  console.log('\x1b[32m[6/6] Creating GitHub Release with zip asset...\x1b[0m');
  run(`gh release create v${newVersion} ${ZIP_NAME} --title "v${newVersion}" --notes "Release v${newVersion}"`);

  // Cleanup
  if (fs.existsSync(ZIP_NAME)) {
    fs.unlinkSync(ZIP_NAME);
  }

  console.log(`\x1b[32m\nSuccessfully deployed version v${newVersion}!\x1b[0m`);
}

main();
