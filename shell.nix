{ pkgs ? import <nixpkgs> {} }:

let
  pythonPackages = pkgs.python311Packages;
in
pkgs.mkShell {
  buildInputs = with pkgs; [

    # openai-whisper-cpp
    # Python with specific version
    # python311
    
    # System dependencies
    ffmpeg  # Required for whisper
    
    # Python packages
    python312Packages.python-telegram-bot
    python312Packages.openai-whisper
    
    # pythonPackages.pip
    # pythonPackages.virtualenv
  ];

}