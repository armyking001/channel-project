const { spawn } = require('child_process');
const path = require('path');
const viteBin = path.join(__dirname, 'node_modules', 'vite', 'bin', 'vite.js');
const child = spawn('node', [viteBin, 'build'], {
  cwd: __dirname,
  stdio: 'inherit',
  shell: true
});
child.on('exit', (code) => process.exit(code || 0));
