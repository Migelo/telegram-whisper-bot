{ pkgs ? import <nixpkgs> {} }:

let
  pythonPackages = pkgs.python311Packages;
in
pkgs.mkShell {
  buildInputs = with pkgs; [

    pre-commit
    
    # System dependencies
    ffmpeg  # Required for whisper
    
    # Python packages
    python312Packages.telethon
    python312Packages.openai-whisper
  ];

}
