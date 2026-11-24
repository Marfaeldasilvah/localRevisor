{
  description = "Nix-develop-flake for LocalRevisor";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs =
    { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };
      python = pkgs.python314.withPackages (ps: with ps; [
        # app
        flask
        openai
        pypdf
        python-dotenv
        # modo BERT (opcional)
        numpy
        torch
        transformers
        safetensors
        tokenizers
        huggingface-hub
      ]);
      localrevisor = pkgs.writeShellApplication {
        name = "localrevisor";
        runtimeInputs = [
          python
          pkgs.ffmpeg
        ];
        text = ''
          if [ ! -f src/main.py ]; then
            echo "Erro: execute a partir da raiz do repositório localRevisor (onde fica src/main.py)." >&2
            exit 1
          fi
          exec python -m flask --app src.main run --debug "$@"
        '';
      };
    in
    {
      packages.${system}.default = localrevisor;

      apps.${system}.default = {
        type = "app";
        program = "${localrevisor}/bin/localrevisor";
      };

      devShells.${system}.default = pkgs.mkShell {
        packages = [
          python
          localrevisor
        ] ++ (with pkgs; [
          ruff
          ffmpeg
          uv
          vscode-html-languageserver
          vscode-css-languageserver
        ]);

        env = {
          FLASK_APP = "src.main";
        };

        shellHook = ''
          export PYTHONPATH="$PWD''${PYTHONPATH:+:$PYTHONPATH}"
        '';
      };
    };
}
