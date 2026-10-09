{
  description = "Temporary GPU bootstrap: Ollama (default) or Tabby";

  inputs = {
    nixos-config.url = "github:BerndDonner/NixOS-Config";
    nixpkgs.follows = "nixos-config/nixpkgs";
  };

  outputs = { nixpkgs, nixos-config, ... }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };

      mkTargetShell = target: secretSets:
        nixos-config.lib.mkPythonDevShell {
          inherit pkgs secretSets;
          extraPackages = with pkgs; [ openssh git ];
          extraShellHook = ''
            export BOOTSTRAP_TARGET=${target}
          '';
          message = "GPU bootstrap target: ${target}";
        };

      ollamaShell = mkTargetShell "ollama" [ "cloudflare" ];
      # Tabby remains a placeholder until its obsolete backup/restore pipeline
      # is migrated. No dummy tokens are put in SOPS or passed to a server.
      tabbyShell = mkTargetShell "tabby" [ ];
    in {
      devShells.${system} = {
        default = ollamaShell;
        ollama = ollamaShell;
        tabby = tabbyShell;
      };
    };
}
