{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = with pkgs; [

    pre-commit
    
    # System dependencies
    ffmpeg  # Required for whisper
    
    # Python 3.12 and packages
    python312
    python312Packages.python-telegram-bot
    python312Packages.openai-whisper
  ];

}