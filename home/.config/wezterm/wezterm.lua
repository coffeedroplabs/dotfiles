local wezterm = require("wezterm")
local config = wezterm.config_builder()

-- Platform detection
local is_windows = wezterm.target_triple:find("windows") ~= nil
local is_darwin = wezterm.target_triple:find("darwin") ~= nil
local is_linux = wezterm.target_triple:find("linux") ~= nil

-- Font
config.font = wezterm.font("Hack Nerd Font")
config.font_size = 13

-- Color scheme
config.color_scheme = "Tokyo Night"

-- Window settings (platform-specific)
if is_darwin then
  config.window_decorations = "RESIZE"
  config.macos_window_background_blur = 20
  config.window_background_opacity = 0.95
elseif is_linux then
  config.window_decorations = "TITLE | RESIZE"
elseif is_windows then
  config.window_decorations = "RESIZE"
end

-- WSL: default to the Ubuntu distribution
if is_windows then
  config.default_domain = "WSL:Ubuntu"
end

-- Tab bar
config.hide_tab_bar_if_only_one_tab = true
config.use_fancy_tab_bar = false

-- Cursor
config.default_cursor_style = "BlinkingBlock"

-- Scrollback
config.scrollback_lines = 10000

return config
