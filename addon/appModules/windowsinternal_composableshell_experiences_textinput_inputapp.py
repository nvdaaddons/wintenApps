# A part of NonVisual Desktop Access (NVDA)
# Copyright (C) 2017-2023 NV Access Limited, Joseph Lee
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
import UIAHandler
import api
from NVDAObjects import NVDAObject


# Built-in modern keyboard app module powers bulk of the below app module class, so inform Mypy.
class AppModule(AppModule):  # type: ignore[no-redef]

	def event_UIA_elementSelected(self, obj: NVDAObject, nextHandler: Callable[[], None]):
		automationId = obj.UIAAutomationId
		# Do not proceed if emoji panel category item is selected when the panel itself is gone.
		# This is the case when closing emoji panel portion in Windows 11.
		if automationId.startswith("navigation-menu-item"):
			focus = api.getFocusObject()
			# System focus restored.
			if focus.appModule != self:
				return
			# NVDA is stuck in a nonexistent edit field.
			# Focus object location can be None sometimes.
			focusLocation = api.getFocusObject().location
			if not any(focusLocation):
				eventHandler.queueEvent("gainFocus", obj.objectWithFocus())
				return
		# NVDA Core takes care of the rest.
		super().event_UIA_elementSelected(obj, nextHandler)

	# Register modern keyboard interface elements with local event handler group.
	def _windowOpenEventInternalEventHandlerGroupRegistration(
			self, firstChild: NVDAObject, firstChildAutomationId: str
	) -> None:
		# Gather elements to be registered inside a list so they can be registered in one go.
		localEventHandlerElements = [firstChild]
		# For dictation, add elements manually so name change event can be handled.
		# Object hierarchy is different in voice typing (Windows 11).
		if firstChildAutomationId in ("DictationMicrophoneButton", "FloatyTip"):
			if firstChildAutomationId == "DictationMicrophoneButton":
				element = firstChild.next
			else:
				element = firstChild.firstChild.firstChild
			while element.next is not None:
				localEventHandlerElements.append(element)
				element = element.next
		# Don't forget to add actual candidate item element so name change event can be handled
		# (mostly for hardware keyboard input suggestions).
		if isinstance(firstChild, ImeCandidateUI):
			imeCandidateItem = firstChild.firstChild.firstChild
			# In Windows 11, an extra element is located between candidate UI window and items themselves.
			if winVersion.getWinVer() >= winVersion.WIN11:
				# For some odd reason, suggested text is the last element.
				imeCandidateItem = imeCandidateItem.lastChild
			localEventHandlerElements.append(imeCandidateItem)
		for element in localEventHandlerElements:
			try:
				# Sometimes traversal fails, resulting in a null element being added.
				# Noticeable when opening Voice Access suggestions in Windows 11 22H2 and later.
				UIAHandler.handler.removeEventHandlerGroup(element.UIAElement, UIAHandler.handler.localEventHandlerGroup)
				UIAHandler.handler.addEventHandlerGroup(element.UIAElement, UIAHandler.handler.localEventHandlerGroup)
			except AttributeError:
				pass

	def event_UIA_window_windowOpen(self, obj: NVDAObject, nextHandler: Callable[[], None]):
		# Ask NVDA to respond to UIA events coming from modern keyboard interface.
		# Focus change event will not work, as it'll cause focus to be lost when the panel closes.
		# This is more so on Windows 10.
		firstChild = obj.firstChild
		# Sometimes window open event is raised when the input panel closes.
		if firstChild is None:
			return
		firstChildAutomationId = firstChild.UIAAutomationId
		# Originally part of this method, split into an internal function to reduce complexity.
		# However, in Windows 11, combined emoji panel and clipboard history moves system focus to itself.
		# Therefore there is no need to add UIA elements to local event handler group.
		try:
			if firstChildAutomationId != "Windows.Shell.InputApp.FloatingSuggestionUI":
				self._windowOpenEventInternalEventHandlerGroupRegistration(firstChild, firstChildAutomationId)
		except NotImplementedError:
			pass
		# Windows 11 22H2 Moment 1 (October 2022) and later uses modern keyboard interface to display
		# Suggested Actions such as Skype calls if data such as phone number is copied to the clipboard.
		# Because keyboard interaction is not possible, just report suggested actions.
		if firstChildAutomationId == "Windows.Shell.InputApp.SmartActionsUX":
			import ui
			suggestedActions = [
				suggestedAction.name for suggestedAction in firstChild.children if suggestedAction.name
			]
			ui.message("; ".join(suggestedActions))
		# NVDA Core takes care of the rest.
		super().event_UIA_window_windowOpen(obj, nextHandler)

	def event_gainFocus(self, obj: NVDAObject, nextHandler: Callable[[], None]):
		# Focus gets stuck in Modern keyboard when clipboard history closes in Windows 11.
		if obj.parent.childCount == 0:
			# Do not queue events if events are pending.
			if not eventHandler.isPendingEvents():
				eventHandler.queueEvent("gainFocus", obj.objectWithFocus())
			return
		nextHandler()
