const { existsSync, readFileSync } = require('node:fs');
const { join } = require('node:path');
const { parseEnv } = require('node:util');

const root = __dirname;
const envFile = join(root, '.env');
const fileEnv = existsSync(envFile) ? parseEnv(readFileSync(envFile, 'utf8')) : {};
const setting = (name, fallback) => fileEnv[name] ?? process.env[name] ?? fallback;
const databaseUrl = setting('DATABASE_URL');
if (!databaseUrl) {
  throw new Error('请先在项目 .env 或环境变量中设置 DATABASE_URL。');
}

module.exports = {
  apps: [{
    name: 'fgas',
    cwd: root,
    script: join(root, '.venv/bin/python'),
    interpreter: 'none',
    args: ['-m', 'uvicorn', 'backend.entrypoints.http:app',
      '--host', '127.0.0.1', '--port', setting('API_PORT', '10622')],
    exec_mode: 'fork',
    instances: 1,
    watch: false,
    autorestart: true,
    time: true,
    env: {
      ...fileEnv,
      PYTHONUNBUFFERED: '1',
      DATABASE_URL: databaseUrl,
      AUTH_MODE: setting('AUTH_MODE', 'development'),
      COOKIE_SECURE: setting('COOKIE_SECURE', 'false'),
    },
  }],
};
