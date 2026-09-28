# CachyOS · Hyprland · Noctalia dots

Configuração pessoal de Hyprland (Lua) e Noctalia no CachyOS, guardada em setembro de 2026. É uma fotografia do setup, não um instalador completo.

## Conteúdo

- `.config/hypr/`: janelas, atalhos, efeitos e integração de cores do Noctalia.
- `.config/noctalia/`: inatividade, modelos de tema e paletas pessoais.
- `.local/share/noctalia-temas/app/`: aplicação GTK4 e gestor de perfis.
- `.local/bin/noctalia-temas`: lançador usado por `SUPER + ALT + T`.

## Utilização

Revê os ficheiros antes de os copiar para `~/` e faz uma cópia das tuas configurações atuais. O setup espera Hyprland com configuração Lua, Noctalia, Foot, Nautilus, Python 3 e PyGObject/GTK4. O gestor de temas procura os perfis em `~/.local/share/noctalia-temas/themes/`; os perfis e wallpapers não foram publicados neste primeiro commit. Podes criar perfis pela interface ou importar do Aether, conforme as dependências presentes no teu sistema. As paletas em `.config/noctalia/palettes/` foram preservadas como dados de cor.

A localização meteorológica e a pasta de capturas não estão incluídas. Configura-as localmente no Noctalia.

## Origem

Preparado a partir dos arquivos pessoais `cachyos-hyprland-dots.tar.gz` e `noctalia-temas.zip`. As cópias de segurança `*.before-*` foram removidas.
