local wezterm = require("wezterm")

local config = wezterm.config_builder()

config.color_scheme = "rose-pine-moon"
config.font = wezterm.font("Hack Nerd Font")
config.font_size = 15.0
config.window_background_opacity = 0.8
config.hide_tab_bar_if_only_one_tab = true

-- Platform-specific settings (Windows-side WezTerm launches WSL; macOS gets
-- blur + RESIZE-only; Linux/WSLg gets TITLE | RESIZE).
local target = wezterm.target_triple
if target:find("windows") then
  config.window_decorations = "TITLE | RESIZE"
  config.default_prog = { "wsl.exe", "--cd", "~" }
elseif target:find("darwin") then
  config.window_decorations = "RESIZE"
  config.macos_window_background_blur = 50
else
  config.window_decorations = "TITLE | RESIZE"
end

return config
