{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = with pkgs; [
    ffmpeg
    (python312.withPackages (ps: with ps; [
      python-telegram-bot
      openai-whisper
    ]))
  ];
}