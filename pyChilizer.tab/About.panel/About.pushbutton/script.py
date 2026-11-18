import webbrowser

from pyrevit import script

# import WPF creator and base Window
import wpf
from System import Windows

__doc__ = 'pyChilizer toolbar'

xamlfile = script.get_bundle_file('AboutWindow.xaml')


class AboutWindow(Windows.Window):
    def __init__(self):
        wpf.LoadComponent(self, xamlfile)

    def handle_url_click(self, sender, args):  # pylint: disable=unused-argument
        """Callback for handling click on package website url"""
        return webbrowser.open_new_tab(sender.NavigateUri.AbsoluteUri)

    def handleclick(self, sender, args):  # pylint: disable=unused-argument
        self.Close()


AboutWindow().ShowDialog()
