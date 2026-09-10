# Automatic Git synchronization

APPROVED: requested by the user on 2026-09-10. The portal is a separate Vercel project, juval-project-intelligence, connected to juvalservicesllc-cloud/JUVAl. Production follows master; preview builds do not replace production. Vercel Authentication protects every deployment and domain.

Every push triggers a build, including changes outside project-portal (ignoreCommand exits 1). The build fetches a separate public checkout and pins it to VERCEL_GIT_COMMIT_SHA. It reuses the existing scanner, regenerates the snapshot, runs portal tests/lint/typecheck, and builds the bilingual site. Failure keeps the existing successful production deployment. Code and evidence SHA must match.

No GitHub token is shipped to the browser. Public GitHub metadata is queried at build time; inaccessible/rate-limited sources are marked unavailable, never zero. Security alerts may require permissions and remain explicitly unavailable in public API builds. Local measured backend results are not committed or fabricated in cloud builds. Linux runtime remains EXTERNAL_RUNTIME_EVIDENCE_REQUIRED.

Refresh reloads the latest published snapshot; it does not write to Git or initiate a deployment. Updates occur on Git pushes, not on local uncommitted changes or a timer. Generated data, environment files, local reports and test artifacts are ignored. No commercial frontend code is changed.

Validation: npm run build:vercel with a full VERCEL_GIT_COMMIT_SHA exercises the same cloud pipeline. Existing model and browser tests cover provenance, separate runtime evidence, bilingual UI and hosted refresh. No new dependency, scheduler or token distribution is needed (Ponytail review).
