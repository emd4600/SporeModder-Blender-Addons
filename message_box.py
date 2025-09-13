import bpy

def show_message_box(message: str, title: str, icon='ERROR'):
	def draw(self, context):
		self.layout.label(text=message)
	bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)

def show_multi_message_box(messages, title: str, icon='ERROR'):
	def draw(self, context):
		for message in messages:
			self.layout.label(text=message)
	bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)
