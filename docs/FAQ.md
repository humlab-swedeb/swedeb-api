## How do I enter Quadlet shell?

```bash
user@pdf-server:~# sudo su -
root@pdf-server:/srv/swedeb_staging# cd /srv/swedeb_staging
root@pdf-server:/srv/swedeb_staging# manage-quadlet shell
```
Replace `swedeb_staging` with the deploy environment you want to enter.

## Update Quadlet configuration

Enter Quadlet shell, then:
```bash
swedeb_staging@pdf-server:~$ pushd configuration/quadlets
swedeb_staging@pdf-server:~$ vi swedeb-staging-app.container
swedeb_staging@pdf-server:~$ popd
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
