{
  description = "dotfiles";

  inputs = {
    # Linux (WSL Ubuntu)
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

    # macOS (nix-darwin pins its own nixpkgs)
    nixpkgs-darwin.url = "github:NixOS/nixpkgs/nixpkgs-26.05-darwin";
    nix-darwin.url = "github:nix-darwin/nix-darwin/nix-darwin-26.05";
    nix-darwin.inputs.nixpkgs.follows = "nixpkgs-darwin";

    # Shared
    home-manager.url = "github:nix-community/home-manager/release-26.05";
    home-manager.inputs.nixpkgs.follows = "nixpkgs";

    nix-homebrew.url = "github:zhaofengli/nix-homebrew";

    herdr.url = "github:ogulcancelik/herdr";
  };

  outputs = inputs@{ self, nixpkgs, nixpkgs-darwin, nix-darwin, nix-homebrew, home-manager, herdr, ... }:
  let
    # The one username line to change if this isn't your machine.
    # bootstrap.sh offers to rewrite this for you if your macOS username differs.
    user = "yashjeetbajwa";

    # --- Linux (WSL Ubuntu): standalone home-manager ---
    linuxSystem = "x86_64-linux";
    linuxPkgs = import nixpkgs {
      system = linuxSystem;
      config.allowUnfree = true;
      overlays = [ herdr.overlays.default ];
    };
  in {
    homeConfigurations.${user} =
      home-manager.lib.homeManagerConfiguration {
        pkgs = linuxPkgs;
        specialArgs = { inherit user; };
        modules = [ ./home.nix ];
      };

    # --- macOS: nix-darwin + home-manager module + nix-homebrew ---
    darwinConfigurations."mac" =
      nix-darwin.lib.darwinSystem {
        system = "aarch64-darwin";
        specialArgs = { inherit user; };
        modules = [
          ./configuration.nix
          nix-homebrew.darwinModules.nix-homebrew
          home-manager.darwinModules.home-manager
          {
            home-manager.useGlobalPkgs = true;
            home-manager.useUserPackages = true;
            home-manager.extraSpecialArgs = { inherit user; };
            home-manager.users.${user} = import ./home.nix;
          }
        ];
      };
  };
}
