
docker build --no-cache -t familyhistories .
docker run --rm familyhistories

cd site
npx quartz build --serve
http://localhost:8080 



python scripts/doit.py data/tree.ged -o site/content/profiles --bios-dir bios


### Understanding the GitHub Actions Workflow
The GitHub Actions workflow (`quartz.yml`) automates the build and deployment process. Here's what it does:
1. **Checkout Repository**: It checks out the code from the `main` branch.
2. **Set up Docker Buildx**: Prepares the environment for building Docker images.
3. **Build Docker Image**: Builds a Docker image named `familyhistories` using the `Dockerfile` in the root directory.
4. **Run Container and Extract Built Site**: Runs a container from the built image, which executes the build process inside the container. The resulting static site files are copied from the container to the host machine.
5. **Upload to GitHub Pages**: Uploads the built site files for deployment to GitHub Pages.
6. **Deploy**: Deploys the site to GitHub Pages.


### Replicating the Build Locally with Docker
You can replicate the build process locally using your Docker setup. Here's how to do it step-by-step:

1. **Ensure Docker is Installed**: Make sure Docker is installed and running on your machine. You can download it from [Docker's official site](https://www.docker.com/get-started) if it's not already installed.

2. **Build the Docker Image**: Open a terminal or command prompt in the root directory of your project (`/c%3A/projects/gedcom2obsidian`). Run the following command to build the Docker image:
   ```bash
   docker build -t familyhistories .
   ```
   This command builds an image named `familyhistories` based on the instructions in your `Dockerfile`. The `Dockerfile` sets up a Node.js environment, installs Python, copies your project files, and defines a default command to run the build process.

3. **Run the Container to Build the Site**: After building the image, run a container to execute the build process. The default command in the `Dockerfile` will convert the GEDCOM file to Markdown notes and build the Quartz static site. Use this command:
   ```bash
   docker run --rm -v "$(pwd)/site/public:/app/site/public" familyhistories
   
   ```
   - `--rm`: Automatically removes the container after it stops.
   - `-v "$(pwd)/site/public:/app/site/public"`: Mounts the local `site/public` directory to the container's `/app/site/public` directory. This ensures that the built site files are saved to your local machine. On Windows, if you're using PowerShell, you might need to adjust the path syntax:
     ```powershell
     docker run --rm -v "${PWD}/site/public:/app/site/public" familyhistories
     ```

   The container will run the command defined in the `Dockerfile`:
   ```bash
   python3 scripts/doit.py data/tree.ged -o site/content/profiles && cd site && set -ex && npx quartz build --verbose
   ```
   This converts the GEDCOM data to Markdown profiles and builds the Quartz site.

4. **Check the Output**: Once the container finishes running, the built static site files will be in the `site/public` directory on your local machine (thanks to the volume mount). You can serve these files locally to preview the site:
   ```bash
   cd site && npx quartz build --serve
   ```
   This will start a local server at `http://localhost:8080` where you can view the site.


### Notes
- **Data File**: Ensure that `data/tree.ged` exists in your project directory, as it's required by the `doit.py` script for generating the profiles.
- **Customizations**: If you need to change the build command or add additional steps, you can override the default command in the `docker run` step by appending a new command, e.g., `docker run --rm -v "$(pwd)/site/public:/app/site/public" familyhistories bash -c "your custom command"`.
- **GitHub Pages Deployment**: The GitHub Actions workflow includes deployment to GitHub Pages, which isn't replicated here. If you want to deploy locally built files, you'll need to manually upload them to your hosting service or set up a separate deployment script.