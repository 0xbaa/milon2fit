{
  description = "Export milon ME training data and upload to Strava";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { nixpkgs, ... }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forAll = f: nixpkgs.lib.genAttrs systems (s: f nixpkgs.legacyPackages.${s});
    in
    {
      devShells = forAll (pkgs: {
        default = pkgs.mkShell {
          packages = with pkgs; [
            just
            jq
            python3
            ruff
            uv
          ];
          env.UV_PYTHON_DOWNLOADS = "never";
          env.UV_PYTHON = "${pkgs.python3}/bin/python3";
        };
      });
    };
}
