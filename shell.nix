{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = with pkgs; [
    ffmpeg
    (python313.withPackages (ps: with ps; [
      telethon
      openai-whisper
    ]))
  ];
}