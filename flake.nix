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
    in
    {
      devShells.${system}.default = pkgs.mkShell {
        buildInputs = [
          python
        ] ++ (with pkgs; [
          ruff
          ffmpeg
          uv
          vscode-html-languageserver
          vscode-css-languageserver
        ]);
      };
    };
}
