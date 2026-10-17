{
  description = "Informal Obligations Utility development environment";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";

  outputs = { nixpkgs, ... }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "aarch64-darwin" ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
    in {
      devShells = forAllSystems (system:
        let pkgs = import nixpkgs { inherit system; };
        in {
          default = pkgs.mkShell {
            packages = with pkgs; [
              nodejs_22
              python312
              uv
              postgresql_17
              gnumake
              git
            ];
            UV_PYTHON_DOWNLOADS = "never";
            # Native Python/Node wheels may need these libraries on NixOS.
            LD_LIBRARY_PATH = pkgs.lib.optionalString pkgs.stdenv.hostPlatform.isLinux
              (pkgs.lib.makeLibraryPath [ pkgs.stdenv.cc.cc.lib pkgs.zlib ]);
            shellHook = ''
              echo "IOU dev shell ready. Run 'make help' for explicit setup/start commands."
            '';
          };
        });
    };
}
