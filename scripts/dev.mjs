import {spawn} from 'node:child_process'
import {existsSync} from 'node:fs'
import {loadEnvFile} from 'node:process'
if(existsSync('.env')) loadEnvFile('.env')
const children=[spawn('bash',['scripts/run-backend.sh'],{stdio:'inherit',env:process.env,detached:true}),spawn('npm',['--prefix','frontend','run','dev'],{stdio:'inherit',env:process.env,detached:true})]
let stopping=false
function stop(code=0){if(stopping)return;stopping=true;for(const child of children){if(child.pid)try{process.kill(-child.pid,'SIGTERM')}catch{}}process.exitCode=code}
for(const signal of ['SIGINT','SIGTERM'])process.on(signal,()=>stop())
for(const child of children){child.on('error',error=>{console.error(error.message);stop(1)});child.on('exit',code=>stop(code || 0))}
