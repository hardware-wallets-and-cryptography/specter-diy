# Submodules Sync

## Troubleshooting: `Unable to find refs/remotes/origin/<branch> revision`

Running `git submodule update --remote` may fail with:

```
fatal: Unable to find refs/remotes/origin/dev revision in submodule path 'bootloader/lib/secp256k1'
```

### Why it happens

[.gitmodules](../../.gitmodules) points the submodules at our forks, each on its
configured branch (usually `dev`, but some use another). However, a submodule that
was cloned earlier keeps the old `origin` URL in its own git config (e.g. upstream
`bitcoin-core/secp256k1`), which has no such branch. Changing `.gitmodules` alone
does not update that remote.

Nested submodules (e.g. `bootloader/lib/secp256k1`, `f469-disco/usermods/secp256k1`)
are configured in the `.gitmodules` of their parent submodule, so every command
below needs `--recursive`.

### Step-by-step fix

1. Check which remote a submodule currently uses:

   ```sh
   git -C bootloader/lib/secp256k1 remote -v
   ```

   If it shows an upstream URL instead of our fork, continue.

2. Verify `.gitmodules` has the expected fork URL and branch
   (use `-f f469-disco/.gitmodules` for that submodule's nested ones):

   ```sh
   git config -f .gitmodules --get-regexp 'submodule\..*\.(url|branch)'
   ```

3. Copy the URLs from `.gitmodules` into each submodule's `origin`.
   This only rewrites remote URLs: it does not fetch or change any checkout.

   ```sh
   git submodule sync --recursive
   ```

4. Make sure every submodule is initialized at the commit pinned by this repo
   (no version change):

   ```sh
   git submodule update --init --recursive
   ```

5. Confirm the result:

   ```sh
   git submodule status --recursive
   ```

   ```sh
   git -C bootloader/lib/secp256k1 remote -v   # should now show the fork
   ```

### Only update repo links (no version bump)

Steps 1-3 are enough: `git submodule sync --recursive` changes only the `origin`
URLs. If the new remote's refs are needed, fetch without moving the checkout:

```sh
git -C <submodule-path> fetch origin
```

### Bumping submodules to the latest branch tip (optional)

Only if you intend to move submodules to the newest commit of their branch, run
these commands from the repository root:

```sh
git submodule sync --recursive
git submodule update --remote --recursive
```

The first command synchronizes local submodule remote URLs with `.gitmodules`.
The second fetches and checks out the latest revisions on configured remote
branches, including nested submodules. This may change submodule pointers, so
review the changes before committing.

Review the changed pins with:

```sh
git submodule status --recursive
git status --short
git diff --submodule=log
```

Commit them only if you intend to bump the submodule versions.

> Tip: whenever a submodule URL changes in `.gitmodules`, run
> `git submodule sync --recursive` before `git submodule update`.
