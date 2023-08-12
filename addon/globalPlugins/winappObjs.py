# Windows app controls repository
# Copyright 2015-2023 Joseph Lee, released under GPL.

# Adds handlers for various UIA controls found in Windows 10 and later.

from typing import List, Optional, Callable
import globalPluginHandler
from NVDAObjects.UIA import Dialog
from NVDAObjects import NVDAObject
import globalVars
import UIAHandler
import ui


# #20: don't even think about proceeding in secure screens.
def disableInSecureMode(cls):
	return globalPluginHandler.GlobalPlugin if globalVars.appArgs.secure else cls


@disableInSecureMode
class GlobalPlugin(globalPluginHandler.GlobalPlugin):

	def __init__(self):
		super().__init__()

	def chooseNVDAObjectOverlayClasses(self, obj: NVDAObject, clsList: List[NVDAObject]) -> None:
		try:
			UIAClassName = obj.UIAElement.cachedClassName
		except AttributeError:
			UIAClassName = ""
		# Windows that are really dialogs.
		# Some dialogs, although listed as a dialog thanks to UIA class name,
		# does not advertise the proper role of dialog.
		# This is still the case with some dialogs such as restart to install updates dialog in Windows 11.
		if UIAClassName in UIAHandler.UIADialogClassNames and Dialog not in clsList:
			clsList.insert(0, Dialog)

	def event_UIA_notification(
			self, obj: NVDAObject, nextHandler: Callable[[], None],
			displayString: Optional[str] = None, activityId: Optional[str] = None, **kwargs
	):
		# In Windows Insider build 22631 (beta)/23493 (dev)/25905 (canary) and later,
		# UIA notification event from File Explorer is used to report virtual desktop names.
		# Reverted to CSRSS name change event in build 23511 (dev) but uses UIA notification in 23521.
		# Handle this event in the global plugin so announcements can be made regardless of focused app.
		if obj.appModule.appName == "explorer" and activityId == "Windows.Shell.TextAnnouncement":
			ui.message(displayString)
			return
		nextHandler()
