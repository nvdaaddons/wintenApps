# Windows app controls repository
# Copyright 2015-2021 Joseph Lee, released under GPL.

# Adds handlers for various UIA controls found in Windows 10 and later.

# Help Mypy and other static checkers for a time by using annotations from future Python releases.
from __future__ import annotations
from typing import Optional, Any
from comtypes import COMError
import globalPluginHandler
import ui
import controlTypes
from NVDAObjects.UIA import UIA, Dialog
# Temporary: test for suggestions list until NVDA 2021.3 requirement is in effect.
import NVDAObjects.UIA
import api
import config
import queueHandler
import eventHandler
import globalVars
import UIAHandler
from logHandler import log
import winVersion
import addonHandler
addonHandler.initTranslation()

# #52: forget everything if the current release is not a supported version of Windows.
isAddonSupported = winVersion.getWinVer() >= winVersion.WIN10_20H2


# For convenience.
additionalEvents: dict[int, str] = {
	UIAHandler.UIA_Drag_DragCompleteEventId: "UIA_dragComplete",
	UIAHandler.UIA_DropTarget_DroppedEventId: "UIA_dropTargetDropped",
	UIAHandler.UIA_LayoutInvalidatedEventId: "UIA_layoutInvalidated",
}


# Suggestions list view.
# Unlike Start menu suggestions, these fire UIA layout invalidated event and top suggestion is not announced.
# At least announce suggestion count.
class SuggestionsListView(UIA):

	def event_UIA_layoutInvalidated(self):
		# Announce number of items found
		# Because inaccurate count could be announced (when users type, suggestion count changes),
		# thus announce this if position info reporting is enabled.
		# However, forget all this if no suggestions are present.
		# This may happen if this event is fired prior to controller for event.
		if self.childCount == 0:
			return
		# In some cases, suggestions list fires layout invalidated event repeatedly.
		# This is the case with Microsoft Store's search field.
		import speech
		speech.cancelSpeech()
		# Item count must be the last one spoken.
		suggestionsCount: int = self.childCount
		suggestionsMessage = (
			# Translators: part of the suggestions count message (for example: 2 suggestions).
			_("1 suggestion")
			# Translators: part of the suggestions count message (for example: 2 suggestions).
			if suggestionsCount == 1 else _("{} suggestions").format(suggestionsCount)
		)
		ui.message(suggestionsMessage)


# Various XAML headings (Settings app, for example) introduced in Windows 10 1803.
UIAHeadingsToNVDAHeadings: dict[int, controlTypes.Role] = {
	UIAHandler.HeadingLevel1: controlTypes.Role.HEADING1,
	UIAHandler.HeadingLevel2: controlTypes.Role.HEADING2,
	UIAHandler.HeadingLevel3: controlTypes.Role.HEADING3,
	UIAHandler.HeadingLevel4: controlTypes.Role.HEADING4,
	UIAHandler.HeadingLevel5: controlTypes.Role.HEADING5,
	UIAHandler.HeadingLevel6: controlTypes.Role.HEADING6,
}


class XAMLHeading(UIA):

	def _get_role(self) -> int:
		return UIAHeadingsToNVDAHeadings[self._getUIACacheablePropertyValue(UIAHandler.UIA_HeadingLevelPropertyId)]


class GlobalPlugin(globalPluginHandler.GlobalPlugin):

	def __init__(self):
		super(GlobalPlugin, self).__init__()
		# Don't do anything unless this is Windows 10 or later.
		# #52: and this is a supported build.
		if not isAddonSupported:
			return
		# #20: don't even think about proceeding in secure screens.
		# #40: skip over the rest if appx is in effect.
		if globalVars.appArgs.secure or config.isAppX:
			return
		# Try adding additional events in the constructor.
		# If it fails, try again after NVDA is fully initialized.
		try:
			log.debug("winapps: adding additional events")
			self._addAdditionalUIAEvents()
		except AttributeError:
			log.debug("winapps: UIA handler not ready, delaying until NVDA is fully initialized")
			queueHandler.queueFunction(queueHandler.eventQueue, self._addAdditionalUIAEvents, delay=True)

	# Manually add events after root element is located.
	def _addAdditionalUIAEvents(self, delay: bool = False) -> None:
		# Add a series of events instead of doing it one at a time.
		# Some events are only available in a specific build range
		# and/or while a specific version of IUIAutomation interface is in use.
		if delay:
			log.debug("winapps: adding additional events after a delay")
		# Use event handler group facility to add more events.
		# Internally powered by IUIAutomation6 interface introduced in Windows 10 1809.
		addonGlobalEventHandlerGroup = UIAHandler.handler.clientObject.CreateEventHandlerGroup()
		for event, name in additionalEvents.items():
			if event not in UIAHandler.UIAEventIdsToNVDAEventNames:
				UIAHandler.UIAEventIdsToNVDAEventNames[event] = name
				# Global event handler group set must be updated, too.
				UIAHandler.globalEventHandlerGroupUIAEventIds.add(event)
				addonGlobalEventHandlerGroup.addAutomationEventHandler(
					event,
					UIAHandler.TreeScope_Subtree,
					UIAHandler.handler.baseCacheRequest,
					UIAHandler.handler
				)
				log.debug(f"winapps: added event ID {event}, assigned to {name}")
		UIAHandler.handler.addEventHandlerGroup(UIAHandler.handler.rootElement, addonGlobalEventHandlerGroup)

	def chooseNVDAObjectOverlayClasses(self, obj, clsList):
		if not isinstance(obj, UIA):
			return
		# Windows that are really dialogs.
		# Some dialogs, although listed as a dialog thanks to UIA class name,
		# does not advertise the proper role of dialog.
		# This is still the case with some dialogs such as restart to install updates dialog in Windows 11.
		if obj.UIAElement.cachedClassName in UIAHandler.UIADialogClassNames and Dialog not in clsList:
			clsList.insert(0, Dialog)
			return
		# Recognize suggestions list view firing layout invalidated event.
		# Although certain list views such as languages list in Settings app fire layout invalidated event,
		# they are not true suggestions list views.
		# NVDA 2021.3 transplants suggestions list class into NVDA Core.
		if obj.UIAAutomationId == "SuggestionsList" and not hasattr(NVDAObjects.UIA, "SuggestionsList"):
			clsList.insert(0, SuggestionsListView)
			return
		# Recognize headings as reported by XAML (Windows 10 1803 or later).
		# Some apps may cause COM to throw timeout error.
		# See older add-on releases for details on COM error handling.
		# NvDA does not recognize heading levels 7, 8, and 9, therefore use a chained comparison.
		if (
			UIAHandler.HeadingLevel1 <= obj._getUIACacheablePropertyValue(
				UIAHandler.UIA_HeadingLevelPropertyId
			) <= UIAHandler.HeadingLevel6
			# But not for apps such as Calculator where doing so results in confusing user experience.
			and obj.appModule.appName not in ("calculator", "calculatorapp")
		):
			clsList.insert(0, XAMLHeading)

	# Record UIA property info about an object if told to do so.
	# An add-on named Event Tracker (deriving from this add-on) will log event information for most events.
	# However, because this add-on adds additional events, log them here.
	def uiaDebugLogging(self, obj: Any, event: Optional[str] = None) -> None:
		if isinstance(obj, UIA) and log.isEnabledFor(log.DEBUG):
			info: list[str] = [f"object: {repr(obj)}"]
			info.append(f"name: {obj.name}")
			if not event:
				event = "no event specified"
			info.append(f"event: {event}")
			info.append(f"app module: {obj.appModule}")
			element = obj.UIAElement
			# Sometimes due to timing errors, COM error is thrown
			# when trying to obtain Automation Id from the underlying UIA element.
			# To keep an eye on this, use cached Automation Id
			# rather than fetching UIAAutomationId property directly.
			# See older add-on releases for details on cached Automation Id.
			info.append(f"Automation Id: {obj.UIAAutomationId}")
			info.append(f"class name: {element.cachedClassName}")
			log.debug(u"winapps: UIA {debuginfo}".format(debuginfo=", ".join(info)))

	# Events defined in NVDA.

	def event_nameChange(self, obj, nextHandler):
		# NVDA Core issue 5641: try catching virtual desktop switch event,
		# which will result in name change for the desktop object.
		# To be taken care of by NVDA Core, and for older releases, let the add-on handle it for a time.
		# This may degrade performance and/or cause NVDA to become verbose in situations other than
		# virtual desktop switch, so exercise discretion.
		if obj.windowClassName == "#32769":
			if log.isEnabledFor(log.DEBUG):
				log.debug(f"winapps: possible desktop name change from {obj}, app module: {obj.appModule}")
			# CSRSS: Client/Server Runtime Subsystem (Windows subsystem process/desktop object)
			if obj.appModule.appName == "csrss":
				import wx
				# Even with desktop name change handler added,
				# older Windows releases won't support this properly.
				# Properly supported in Windows 10 1909.
				if not hasattr(eventHandler, "handlePossibleDesktopNameChange"):
					wx.CallLater(500, ui.message, obj.name)
		nextHandler()

	def event_liveRegionChange(self, obj, nextHandler):
		# No, do not let Start menu size be announced.
		# Moved from Shell Experience Host in 2018 as a different app hosts this control in build 18282.
		if isinstance(obj, UIA) and obj.UIAAutomationId == "FrameSizeAccessibilityField":
			return
		nextHandler()

	def event_UIA_notification(self, obj, nextHandler, activityId=None, **kwargs):
		# Introduced in Windows 10 1709, to be treated as a notification event.
		# Bulk of this transferred to Event Tracker add-on in 2021.
		# Play a debug tone if and only if notifications come from somewhere other than the active app
		# and NVDA was restarted with debug logging mode.
		if (
			isinstance(obj, UIA)
			and obj.appModule != api.getFocusObject().appModule
			and globalVars.appArgs.debugLogging
		):
			import tones
			# For debugging purposes.
			tones.beep(500, 100)
		# In recent versions of Word 365, notification event is used to announce editing functions,
		# some of them being quite anoying.
		if obj.appModule.appName == "winword" and activityId in ("AccSN1", "AccSN2"):
			return
		# Do not allow notification to be announced if "report notifications" is off.
		if not config.conf["presentation"]["reportHelpBalloons"]:
			return
		nextHandler()

	# Events defined in this add-on.

	def event_UIA_dragComplete(self, obj, nextHandler):
		self.uiaDebugLogging(obj, "dragComplete")
		# Announce the new drop location by faking a gain focus event.
		eventHandler.queueEvent("gainFocus", obj)
		nextHandler()

	def event_UIA_dropTargetDropped(self, obj, nextHandler):
		self.uiaDebugLogging(obj, "dropTargetDropped")
		# Unlike drag complete event, it is something else that raises this event
		# but NVDA records the correct focused element, so fake a gain focus event.
		eventHandler.queueEvent("gainFocus", api.getFocusObject())
		nextHandler()
