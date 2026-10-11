# Deployment readiness — checked 2026-10-11 (KST)

Initial readiness inspection was read-only; authorized deployment and live validation followed, recorded below. All cloud commands explicitly used project `viberick`, account `jaeho.shin@viberick.com`, and Cloud Run region `asia-northeast3`. No secret payloads, credential values, or complete environment configurations were read.

## Current deployed state after authorized validation

- API `viberick-dub-00010-rih` serves **100% production traffic**; worker and API use `sha256:8d31316651e39f038847ce9e4b0bda82654868f40f2554645bb1b5e0ffff7894`.
- Service origin and Firebase `/api/health` both returned `{"ok":true}` after promotion.
- Exact-text live revalidation passed; manual wording stayed byte-for-byte identical while a shorter utterance produced an explicit underfill warning.
- Hosting, public sample/showcase records, and lifecycle policy were not changed by this backend deployment lane. Parent owns Hosting and demo publication decisions.
- Rollback revision and immutable image remain recorded below.

## Observed production before upgrade

| Component | Current setting |
|---|---|
| API service | `viberick-dub` (not `viberick-dub-api`) |
| API URL | `https://viberick-dub-5piobibujq-du.a.run.app` |
| Serving revision | `viberick-dub-00008-c5x`, 100% traffic |
| API resources | 1 vCPU, 1 GiB, concurrency 80, timeout 300 seconds |
| Worker job | `viberick-dub-worker`, command `python -m dub.worker` |
| Worker resources | 4 vCPU, 8 GiB, timeout 3600 seconds, max retries 0, task count 1 |
| Worker parallelism | No explicit parallelism field returned; task count is 1 |
| API + worker identity | `viberick-dub@viberick.iam.gserviceaccount.com` |
| Both image tags | `asia-northeast3-docker.pkg.dev/viberick/viberick-dub/app:v9` |
| API resolved digest and current v9 registry digest | `sha256:5405d361e69fd8869ebe2664dfc9bb4bee0333d4c59c19c91615dfa3ecf7c64f` |

Immutable rollback image:

```text
asia-northeast3-docker.pkg.dev/viberick/viberick-dub/app@sha256:5405d361e69fd8869ebe2664dfc9bb4bee0333d4c59c19c91615dfa3ecf7c64f
```

The service revision confirms its actual resolved digest. For the worker, its configured tag and that tag's current registry digest were inspected; the digest of a previous worker execution was not inspected.

## Permissions and storage evidence

- Private snapshot bucket `viberick-dub-lab`: Seoul; uniform bucket-level access enabled. Bucket IAM has **no `allUsers` or `allAuthenticatedUsers` binding**. Project IAM also returned no public-principal binding. Thus no public access grant was observed at the inspected bucket/project levels; object ACLs cannot override uniform access.
- Public access prevention is `inherited`, not explicitly `enforced`. This is a hardening opportunity, not an observed public grant. No organization/folder IAM was inspected.
- Runtime identity has `roles/storage.objectAdmin` on `viberick-dub-lab`: sufficient for private workspace upload and restore. It also has `roles/storage.objectAdmin` on `viberick-dub-public`.
- `viberick-dub-public` intentionally grants `roles/storage.objectViewer` to a public principal. **Draft preview audio/video and final outputs are public by link.** Unaccepted previews are not private.
- Runtime identity has project `roles/datastore.user`: sufficient for Firestore jobs, denied-to-client `job_access`, quotas, transactions, and edit documents through the server SDK. Firestore client security rules do not restrict the server IAM identity.
- Runtime identity has `roles/run.jobsExecutorWithOverrides`: sufficient for the API's job execution with `JOB_ID` / `EDIT_ID` overrides.
- Other observed project runtime roles: `roles/aiplatform.user`, `roles/logging.logWriter`, `roles/secretmanager.secretAccessor`, `roles/speech.client`. Only role metadata was inspected, never secret payloads.
- **No missing runtime IAM grant was identified for the new snapshot, ownership, quota, or preview workflows.** This is IAM evidence, not proof that a new deployment has executed successfully.
- No lifecycle configuration was returned for the private lab bucket. New `workspaces/` snapshots therefore have no verified automatic retention. Add a prefix-limited retention rule after reviewing existing bucket policies; do not apply a whole-bucket deletion rule to voice embeddings or STT assets.

## Upgrade sequence (commands prepared, not executed)

Require the parent's final release review before any command below. Preserve existing secret bindings and environment settings: do not replace them with a full environment list.

1. Finish local tests, browser acceptance, and consented paid validation. Use a new immutable image tag; do not overwrite `v9`. Build from this repository:

```sh
gcloud builds submit --tag=asia-northeast3-docker.pkg.dev/viberick/viberick-dub/app:review-20261010 --project=viberick --account=jaeho.shin@viberick.com
```

2. Record the new digest using `gcloud artifacts docker images describe` and use that digest for both updates. The commands below use the candidate tag for readability; replace it with the recorded digest during release.

```sh
gcloud run jobs update viberick-dub-worker --image=asia-northeast3-docker.pkg.dev/viberick/viberick-dub/app:review-20261010 --region=asia-northeast3 --project=viberick --account=jaeho.shin@viberick.com

gcloud run deploy viberick-dub --image=asia-northeast3-docker.pkg.dev/viberick/viberick-dub/app:review-20261010 --no-traffic --region=asia-northeast3 --project=viberick --account=jaeho.shin@viberick.com
```

3. Deploy the explicit private-collection Firestore rules with the VibeRick account. Local rules deny client reads/writes to `job_access` and `quotas`; existing public job reads remain.

```sh
firebase deploy --only firestore:rules --project viberick --account jaeho.shin@viberick.com
```

4. Inspect the candidate API revision readiness, verify its image digest, and validate the worker with a short consented input within the approved budget. Verify ownership rejection, atomic quotas, per-language playback, source/dub timings, generated preview → audition → accept, discard, stale-lease recovery, and original-output preservation before accept. Do not run a borrowed public figure's voice as a cloned speaker.
5. After approval, move API traffic to the reviewed candidate revision and deploy the compatible web files. Replace `REVIEWED_REVISION` with the observed candidate revision name.

```sh
gcloud run services update-traffic viberick-dub --to-revisions=REVIEWED_REVISION=100 --region=asia-northeast3 --project=viberick --account=jaeho.shin@viberick.com
firebase deploy --only hosting:viberick-dub --project viberick --account jaeho.shin@viberick.com
```

Default new controls: 40 billable operations per UTC day (`DUB_DAILY_CAP`), five preview attempts per job (`DUB_JOB_EDIT_CAP`), 20-second heartbeat, 180-second running lease, 600-second queue expiry. Failed dispatched previews still consume quota. Create retries with the same persisted request key, owner token, and normalized payload recover the original job without dispatch or quota consumption; a guessed key alone cannot recover it. Old jobs without an owner token stay read-only. Source/media snapshots use the existing private lab bucket; draft audio/video use versioned paths in the public output bucket.

## Rollback (only if authorized release needs reversal)

```sh
gcloud run services update-traffic viberick-dub --to-revisions=viberick-dub-00008-c5x=100 --region=asia-northeast3 --project=viberick --account=jaeho.shin@viberick.com

gcloud run jobs update viberick-dub-worker --image=asia-northeast3-docker.pkg.dev/viberick/viberick-dub/app@sha256:5405d361e69fd8869ebe2664dfc9bb4bee0333d4c59c19c91615dfa3ecf7c64f --region=asia-northeast3 --project=viberick --account=jaeho.shin@viberick.com
```

Restore the previous Hosting release through Firebase Hosting release history if the UI also changed. Preserve Firestore data, private snapshots, public output versions, and the denied private-collection rules; rollback does not require deleting user jobs or exposing ownership records. Running job executions are not replaced by updating a job's image.

## Prepared private snapshot retention (not applied)

`private-workspace-lifecycle.json` is a seven-day deletion rule matching **only `workspaces/`**. It excludes voice embeddings, STT objects, and every other prefix. Re-read bucket lifecycle immediately before applying and merge any preexisting rules rather than replacing them. Cloud Storage age is measured from each object's creation; cleanup is asynchronous. Each accepted edit's new workspace gets its own seven-day lifetime. After expiry, generation remains playable in public storage for its separate retention period, but line regeneration will need a new source run.

Only after approval and confirming this file retains any other required lifecycle rules:

```sh
gcloud storage buckets update gs://viberick-dub-lab --lifecycle-file=docs/review-2026-10-10/private-workspace-lifecycle.json --project=viberick --account=jaeho.shin@viberick.com
```

This command has **not** been executed.

## Candidate deployment and live smoke — 2026-10-11 KST

With explicit deployment authorization, the worker was updated to digest `sha256:ab2071ba69f555a0eff8523fab6dbf6cd436efa7bf4d4ff162e4092cb12b7962`. API revision `viberick-dub-00009-hij` was deployed with **0% production traffic**, tag `review`, at `https://review---viberick-dub-5piobibujq-du.a.run.app`. Firestore rules compiled and released successfully. Hosting, public showcase records, and bucket lifecycle were not changed.

A non-showcase 12-second English smoke job (`Fty2sz3dBwU-22c37d`) completed with two initial synthesized lines. Same-key/token replay recovered the same job, unauthorized editing returned 403, original and target video/audio/captions/timeline URLs were retrievable, and private workspace restore enabled two previews. Accept advanced revision 0→1; discard preserved revision 1 and accepted output pointers. Evidence is in ignored `runs/cloud-smoke-2026-10-11/evidence.json`; private owner state is kept separately and must not be published.

The shared budget ledger reserved **$10 as one aggregate cloud-smoke allowance under the existing `text` category**. This is conservative admission accounting, not ten dollars of measured charges or one actual text API call. Initial create plus two preview operations were executed; no retry job was created.

**Traffic promotion held:** the live manual-edit test found that underfill repair silently lengthened requested wording. The resulting audio passed automated checks but did not match the exact submitted sentence. A preserve-user-text fix and exact-text live revalidation are required before promoting the candidate. The old API revision remains at 100% production traffic pending that check.


## Corrected release promoted — 2026-10-11 KST

The preserve-user-text fix was rebuilt into immutable digest `sha256:8d31316651e39f038847ce9e4b0bda82654868f40f2554645bb1b5e0ffff7894`, applied to the worker, and deployed as API candidate `viberick-dub-00010-rih` with zero traffic initially.

A third preview on the same smoke job used the exact sentence that previously triggered silent lengthening. The requested and generated row text were both:

> Today, let's clearly explain three concepts: SEO, AEO, and GEO.

The audio/content/meaning check passed. The result correctly reported `Manual text preserved; speech underfills its slot.` instead of silently adding words. The preview was discarded; accepted revision 1 and published output pointers were unchanged. Source and translated artifact URLs remained retrievable. Unauthenticated reads of the smoke job's private ownership record and daily quota document returned HTTP 403.

After this validation, explicit authorization was used to promote `viberick-dub-00010-rih` to **100% traffic**. A subsequent service describe confirmed the traffic assignment, and both Cloud Run origin and Firebase-routed API health checks returned success.

An additional **$5 aggregate reservation** covered the single exact-text revalidation, making the cloud-smoke allowance **$15 total**. The shared ledger snapshot after validation was $81.60 committed / $18.40 remaining under the $100 cap, with no over-budget flag. These are conservative allowance totals including other validation work, not final cloud invoices. No automatic refund was made from unmeasured usage.
