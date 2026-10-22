import { spawnSync } from 'node:child_process';
import config from '../ecosystem.config.cjs';

// Explicit first-time initialization only; PM2 starts Uvicorn directly.
const app = config.apps[0];
const result = spawnSync(app.script, ['-m', 'backend.application.initialize'], {
  cwd: app.cwd,
  env: { ...process.env, ...app.env },
  stdio: 'inherit',
});
if (result.error) throw result.error;
process.exitCode = result.status ?? 1;
