FROM nixos/nix

# Copy Nix configuration files
COPY shell.nix /app/
COPY .envrc /app/

WORKDIR /app

# Install and configure Nix
RUN nix-channel --add https://nixos.org/channels/nixpkgs-unstable nixpkgs && \
    nix-channel --update

COPY main.py /app/

# Use nix-shell to run python main.py as the entry point
CMD ["nix-shell", "--run", "python main.py"]
