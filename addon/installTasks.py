# WinTenApps/installTasks.py
# Copyright 2016-2021 Joseph Lee, released under GPL.

# Provides needed routines during add-on installation and removal.
# Mostly checks compatibility.
# Routines are partly based on other add-ons,
# particularly Place Markers by Noelia Martinez (thanks add-on authors).

import addonHandler
addonHandler.initTranslation()


def onInstall():
	import gui
	import wx
	import winVersion
	currentWinVer = winVersion.getWinVer()
	# For now only check Windows 10.
	minimumSupportedRelease = winVersion.WIN10_20H2
	minimumSupportedReleaseName = "Windows 10 20H2"
	addonInstallPossible = True
	addonInstallErrorMessage = ""
	# Windows App Essentials requires Windows 10 or later.
	if currentWinVer < winVersion.WIN10:
		addonInstallErrorMessage = _(
			# Translators: Dialog text shown when trying to install the add-on on releases earlier than Windows 10.
			"You are using an older version of Windows. This add-on requires Windows 10 or later."
		)
		addonInstallPossible = False
	# Windows App Essentials does not support old feature updates.
	# This is the case for Windows 10 (to be expanded to Windows 11 in the future).
	elif winVersion.WIN10 <= currentWinVer < minimumSupportedRelease:
		addonInstallErrorMessage = _(
			# Translators: Dialog text shown when trying to install the add-on on an unsupported Windows 10 release
			# (minSupportedVersion is the minimum Windows 10 release required for this add-on).
			"You are using an unsupported Windows 10 release. This add-on requires {minSupportedVersion} or later."
		).format(minSupportedVersion=minimumSupportedReleaseName)
		addonInstallPossible = False
	if not addonInstallPossible:
		gui.messageBox(
			addonInstallErrorMessage,
			# Translators: title of the error dialog shown when trying to install the add-on in unsupported systems.
			# Unsupported systems include Windows versions earlier than 10 and old Windows 10 feature updates.
			_("Unsupported Windows release"), wx.OK | wx.ICON_ERROR
		)
		raise RuntimeError("Attempting to install Windows App Essentials on unsupported Windows release")
	# Although installation on server systems is possible, Windows App Essentials does not support it fully.
	# Therefore display a warning message if running on servers.
	if currentWinVer.productType != "workstation":
		gui.messageBox(
			_(
				# Translators: warning text shown when trying to install the add-on on server computers.
				"This is a Windows Server system. Although you can install the add-on, not all features will work."
			),
			# Translators: title of the warning dialog shown when trying to install the add-on on server systems.
			_("Windows App Essentials and Windows Server"), wx.OK | wx.ICON_WARNING
		)
	# Temporary: warn stable release users about experimental support for Windows 11
	# (dev channel subscribers will not receive warnings).
	isWin11 = winVersion.getWinVer().build >= 22000
	warnWin11Experimental = False
	for addon in addonHandler.getAvailableAddons():
		if addon.name == "wintenApps" and addon.isPendingInstall:
			warnWin11Experimental = isWin11 and not addon.version.endswith("-dev")
			break
	if warnWin11Experimental:
		# THIS WARNING DIALOG WILL NOT BE TRANSLATED!
		gui.messageBox(
			"You are using Windows 11 Insider Preview. Support for Windows 11 is experimental "
			"and features can change without notice prior to its general release.",
			"Windows 11 support notice", wx.OK | wx.ICON_WARNING
		)
