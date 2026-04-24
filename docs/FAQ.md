Replace `swedeb_staging` with the deploy environment you want are working with.

## How do I enter Quadlet shell?

```bash
user@pdf-server:~# sudo su -
root@pdf-server:/srv/swedeb_staging# cd /srv/swedeb_staging
root@pdf-server:/srv/swedeb_staging# manage-quadlet shell
```

## Update Quadlet configuration

The Swedeb Quadlet container files are version controlled in the backend's docker folder/quadlets. Please make changes to these files, then copy then to the target environment.

```bash
swedeb_staging@you:~$ scp -R youruser@mydevserver:/path/to/quadlets .
swedeb_staging@you:~$ scp youruser@mydevserver:/path/to/config.yml config.yml
swedeb_staging@you:~$ sudo cp quadlets/* /srv/swedeb_staging/configuration/quadlets
swedeb_staging@you:~$ sudo chown -R swedeb_staging:swedeb_staging /srv/swedeb_staging/configuration/quadlets
swedeb_staging@pdf-server:~$ manage-quadlet install
```
Or manual emergency edit:
```bash
swedeb_staging@pdf-server:~$ vi configuration/quadlets/swedeb-staging-app.container
swedeb_staging@pdf-server:~$ manage-quadlet remove
swedeb_staging@pdf-server:~$ manage-quadlet install
```

## How do I update Swedeb image on PDF-server?

Enter Quadlet shell, then:

```bash
swedeb_staging@pdf-server:~$ podman image pull ghcr.io/humlab-swedeb/swedeb-api:staging
manage-quadlet remove
manage-quadlet install
```

Replace `staging` with the version you want to update (e.g. `latest` or specific version)

## How do I open a shell in a container?

Enter Quadlet shell, then:

```bash
swedeb_staging@pdf-server:~$ podman ps
#  ---> find container and it's ID xyz
swedeb_staging@pdf-server:~$ podman exec -it "xyz" /bin/bash
```
