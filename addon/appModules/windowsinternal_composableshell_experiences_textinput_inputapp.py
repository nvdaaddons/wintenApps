# A part of NonVisual Desktop Access (NVDA)
# Copyright (C) 2017-2024 NV Access Limited, Joseph Lee
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.

# The add-on version of this module will extend the one that comes with NVDA Core.

from typing import Callable
# Yes, this app module is powered by built-in modern keyboard (TextInputHost) app module
# (formerly WindowsInternal.ComposableShell.Experiences.TextInput.InputApp).
# #70: NVDA Core pull requests are made using the core app module, not alias modules.
from nvdaBuiltin.appModules.windowsinternal_composableshell_experiences_textinput_inputapp import (
	AppModule, ImeCandidateUI
)
import winVersion
import eventHandler
import api
import ui
import config
import versionInfo
from NVDAObjects import NVDAObject


# Built-in modern keyboard app module powers bulk of the below app module class, so inform Mypy.
class AppModule(AppModule):  # type: ignore[no-redef]

	def event_UIA_elementSelected(self, obj: NVDAObject, nextHandler: Callable[[], None]):
		# NVDA Core issue 16346: do not proceed if emoji panel category item is selected
		# when the panel is closed in Windows 11.
		if obj.UIAAutomationId.startswith("navigation-menu-item"):
			if (
				# System focus restored.
				(focus := api.getFocusObject()).appModule != self
				# A different part of emoji panel is selected.
				or api.getNavigatorObject() == obj
				# Repeat announcement due to pending gain focus event on category entries.
				or eventHandler.isPendingEvents("gainFocus")
				# System focus is located in GIF/kaomoji/symbol entry.
				or focus.UIAAutomationId.startswith("item-")
			):
				return
			if (
				# NVDA is stuck in a nonexistent edit field (location is None).
				not any(focus.location)
				# Focus is once again stuck in top-level modern keyboard window
				# after switching to clipboard history from other emoji panel screens.
				or focus.firstChild and focus.firstChild.UIAAutomationId == "Windows.Shell.InputApp.FloatingSuggestionUI"
			):
				eventHandler.queueEvent("gainFocus", obj.objectWithFocus())
				return
		# NVDA Core takes care of the rest.
		super().event_UIA_elementSelected(obj, nextHandler)

	def event_gainFocus(self, obj: NVDAObject, nextHandler: Callable[[], None]):
		# NVDA Core issue 16347: focus gets stuck in Modern keyboard
		# when clipboard history closes in Windows 11.
		if obj.firstChild and obj.firstChild.UIAAutomationId == "Windows.Shell.InputApp.FloatingSuggestionUI":
			# Do not queue events if events are pending.
			if not eventHandler.isPendingEvents():
				eventHandler.queueEvent("gainFocus", obj.objectWithFocus())
			return
		nextHandler()

	def event_focusEntered(self, obj: NVDAObject, nextHandler: Callable[[], None]):
		# NVDA Core issue 14023: announce visible IME candidates.
		if (
			isinstance(obj, ImeCandidateUI)
			and obj.parent.UIAAutomationId == "IME_Candidate_Window"
			and config.conf["inputComposition"]["autoReportAllCandidates"]
		):
			ui.message(obj.firstChild.visibleCandidateItemsText)
		nextHandler()

	# The following event handlers are hidden if NVDA 2024.2 or later is running.
	if (versionInfo.version_year, versionInfo.version_major) < (2024, 2):
		def event_UIA_window_windowOpen(self, obj: NVDAObject, nextHandler: Callable[[], None]):
			# NVDA Core issue 16283: announce the first candidate
			# (hardware keyboard input suggestion or IME candidate) in Windows 11.
			# Resolved in NVDA 2024.2.
			if (
				winVersion.getWinVer() >= winVersion.WIN11
				and obj.firstChild and obj.firstChild.UIAAutomationId == "IME_Prediction_Window"
			):
				obj.firstChild.firstChild.firstChild.reportFocus()
			# NVDA Core takes care of the rest.
			super().event_UIA_window_windowOpen(obj, nextHandler)

		def event_UIA_notification(
				self,
				obj: NVDAObject,
				nextHandler: Callable[[], None],
				displayString: str | None = None,
				activityId: str | None = None,
				**kwargs
		):
			# NVDA Core issue 16009: Windows 11 uses modern keyboard interface to display Suggested Actions
			# such as Skype calls when data such as phone number is copied to the clipboard.
			# Because keyboard interaction is not possible, just report the top suggested action.
			# Resolved in NVDA 2024.2.
			if activityId == "Windows.Shell.InputApp.SmartActions.Popup":
				displayString = obj.name
			ui.message(displayString)
