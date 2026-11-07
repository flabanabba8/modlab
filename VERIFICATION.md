# Verification

- Twelve synthetic Linux tests passed for guarded ZIP application, replacement consent, file identity, rollback, preserved revision selection, locking, safe timestamp fallback and a self-authored executable fixture.
- An initial native Windows run failed because `utime` lacked no-follow support. After the safe fallback, native Windows synthetic copy, replacement approval, rollback, root and nested junction rejection, cross-process locking and writable copies of read-only source files passed. Timestamps are not preserved where safe no-follow updates are unavailable; Windows ACLs and adversarial symlink races were not tested.
- A separate read-only test copied an existing local game distribution into a temporary lab, applied a synthetic marker file to a new revision, rolled back and verified the original executable's hash was unchanged. The game was not launched and no original installation was modified.
- This file-handling check does not establish that a copied game launches, that a real mod works, or that external saves and installers are handled. Broader Windows behavior, a reviewed demonstration and the full publication audit remain unverified.
