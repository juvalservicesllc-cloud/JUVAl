import {copyFileSync,mkdirSync} from 'node:fs';
import {resolve} from 'node:path';
import {portal,output} from './sync.mjs';
mkdirSync(resolve(portal,'public'),{recursive:true});
copyFileSync(output,resolve(portal,'public/project-state.json'));
console.log('Offline snapshot prepared from the last successful sync.');
