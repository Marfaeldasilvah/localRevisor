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
      docsServe = pkgs.writeShellApplication {
        name = "docs-serve";
        runtimeInputs = [
          pkgs.mdbook
          pkgs.mdbook-mermaid
        ];
        text = ''
          if [ ! -f DOCS.md ]; then
            echo "Erro: execute a partir da raiz do repositório localRevisor (onde fica DOCS.md)." >&2
            exit 1
          fi

          workdir="$(mktemp -d)"
          trap 'rm -rf "$workdir"' EXIT

          mkdir -p "$workdir/src"
          ln -s "$PWD/DOCS.md" "$workdir/src/DOCS.md"
          printf '# Sumário\n\n- [Pipeline e Arquitetura (DOCS)](DOCS.md)\n' > "$workdir/src/SUMMARY.md"
          if [ -f "$PWD/README.md" ]; then
            ln -s "$PWD/README.md" "$workdir/src/README.md"
            printf -- '- [README](README.md)\n' >> "$workdir/src/SUMMARY.md"
          fi

          cat > "$workdir/book.toml" <<'EOF'
          [book]
          title = "localRevisor — Documentação"
          language = "pt-BR"
          src = "src"

          [output.html]
          default-theme = "light"
          preferred-dark-theme = "navy"
          EOF

          mdbook-mermaid install "$workdir" >/dev/null
          mdbook serve "$workdir" -n 127.0.0.1 "$@"
        '';
      };
    in
    {
      packages.${system} = {
        default = localrevisor;
        DOCS = docsServe;
      };

      apps.${system} = {
        default = {
          type = "app";
          program = "${localrevisor}/bin/localrevisor";
        };
        DOCS = {
          type = "app";
          program = "${docsServe}/bin/docs-serve";
        };
      };

      devShells.${system} = {
        default = pkgs.mkShell {
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

        DOCS = pkgs.mkShell {
          packages = [
            docsServe
            pkgs.mdbook
            pkgs.mdbook-mermaid
            pkgs.glow
          ];

          shellHook = ''
            echo "Ambiente de documentação (DOCS.md + Mermaid) pronto:"
            echo "  docs-serve        # abre preview HTML com Mermaid em http://127.0.0.1:3000"
            echo "  docs-serve --open # abre automaticamente no navegador"
            echo "  glow DOCS.md      # leitura rápida no terminal"
          '';
        };
      };
    };
}
