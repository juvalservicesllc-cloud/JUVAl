import {execFileSync} from 'node:child_process';
import {mkdtempSync,mkdirSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {resolve} from 'node:path';
const sha=process.env.VERCEL_GIT_COMMIT_SHA;
if(!sha||!/^[a-f0-9]{40}$/.test(sha))throw new Error('A full Vercel Git commit SHA is required; refusing to publish stale evidence.');
const directory=mkdtempSync(resolve(tmpdir(),'juval-evidence-'));
// The public repository needs no credential. A separate checkout makes builds
// independent of Vercel source archives omitting .git and monorepo parent files.
execFileSync('git',['clone','--quiet','https://github.com/juvalservicesllc-cloud/JUVAl.git',directory],{timeout:120000,stdio:'pipe',windowsHide:true});
execFileSync('git',['checkout','--quiet','--detach',sha],{cwd:directory,timeout:30000,stdio:'pipe',windowsHide:true});
process.env.JUVAL_EVIDENCE_ROOT=directory;
process.env.JUVAL_EVIDENCE_REF=sha;
const {portal,generate}=await import('./sync.mjs');
mkdirSync(resolve(portal,'data/generated'),{recursive:true});
const {githubSnapshot}=await import('./github.mjs');
await githubSnapshot();
const state=generate();
if(state.git.head!==sha)throw new Error('Evidence revision does not match the deployed code.');
console.log(`Git snapshot rebuilt: ${sha}; ${state.adrs.length} ADRs; ${state.files.length} sources.`);
