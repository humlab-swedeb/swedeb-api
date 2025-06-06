
### 1. Basic Build Command

This command builds the image using the default values specified in the Dockerfile (`UID=1021`, `GID=1021`) and tags it as `cwb-base:latest`.

```bash
docker build -t cwb-base:latest .
```

*   `docker build`: The command to build an image from a Dockerfile.
*   `-t cwb-base:latest`: The `-t` or `--tag` flag assigns a name and a tag to the image. Here, the name is `cwb-base` and the tag is `latest`. You could use a more specific tag, like `cwb-base:3.5.0-py3.12`.
*   `.`: This specifies the build context (the current directory), which is where Docker will look for the `Dockerfile` and any other files needed for the build.

---

### 2. Recommended Build Command (for Development)

This is the recommended command for a development environment, especially if you plan to mount local directories into the container (e.g., for corpus data). It sets the container's user ID (UID) and group ID (GID) to match your current host user. This prevents file permission issues when the container writes to mounted volumes.

```bash
docker build \
  --build-arg CWB_UID=$(id -u) \
  --build-arg CWB_GID=$(id -g) \
  -t cwb-base:latest .
```

*   `--build-arg CWB_UID=$(id -u)`: This sets the `CWB_UID` build argument. The `$(id -u)` command dynamically gets your current user's ID on Linux or macOS.
*   `--build-arg CWB_GID=$(id -g)`: This does the same for your user's group ID.
*   **Why is this better?** When you run the container and mount a volume like `-v ./my_corpus_data:/data`, any files created inside the container in the `/data` directory will be owned by `cwbuser`. By matching the UIDs, `cwbuser` inside the container will have the same ID as your user on the host, so you can easily edit or delete those files outside the container without `sudo`.

---

### How to Use the Built Image

Once the build is complete, you can run the container.

#### To get an interactive Bash shell inside the container:
This is perfect for running `cqp`, `cwb-encode`, etc., manually.

```bash
docker run -it --rm \
  -v "$(pwd)/corpus_files:/data" \
  cwb-base:latest
```
*   `-it`: Runs the container in interactive mode with a TTY, giving you a shell.
*   `--rm`: Automatically removes the container when you exit, keeping your system clean.
*   `-v "$(pwd)/corpus_files:/data"`: Mounts a local directory named `corpus_files` into the container at the `/data` path. This is where you would put your corpus registry and data files.
*   `cwb-base:latest`: The name of the image you want to run.

Inside this shell, you can now run your CWB commands:
```bash
# Inside the container
cqp -v
cwb-encode -d /data/registry -f my_source_file.vrt -R /data/registry/my_corpus
```

#### To run a specific command directly (non-interactively):
This is useful for scripting. For example, to check the version of `cwb-align`.

```bash
docker run --rm cwb-base:latest cwb-align -v
```

This will start the container, run `cwb-align -v`, print the output, and then the container will be removed.