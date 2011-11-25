#!/usr/bin/python
import ConfigParser
import sys
import os
import pygtk
pygtk.require("2.0")
import gtk
import sqlite3
import gtk.glade
import json
import time
import re
import pango

textTags = {
	"<nl::title>":["title",[["font","Serif 14"], ["underline", pango.UNDERLINE_SINGLE]]],
	"<nl::ital>":["ital",[["style", pango.STYLE_ITALIC]]],
	"<nl::bold>":["bold",[["weight", 700]]],
	"<nl::red>":["red",[["foreground","red"]]],
	"<nl::link>":["link",[["underline", pango.UNDERLINE_SINGLE],["foreground", "blue"]]],
	"<nl::noteLink>":["noteLink",[["editable", False],["foreground","blue"],["underline", pango.UNDERLINE_SINGLE]]],
	"<nl::viewBlock>":["viewBlock",[["editable", False]]],
	"<nl::inlineTitle>":["inlineTitle", [["weight", 700],["underline", "single"]]],
	"<nl::viewLink>":["viewLink", [["editable", False]]]
}

tagsNoMarkup = {
	"invisible": [["invisible", True]],
	"visible": [["invisible", False]],
	"expandMark": [["editable", False],["weight", 700]],
	"shrinkMark": [["editable", False],["weight", 700]],
	"delMark": [["editable", False],["weight", 700],["foreground","red"]],
	"underline": [["underline", pango.UNDERLINE_SINGLE]],
	"viewTitle": [["font","Sans 12"],["editable", False],["foreground","blue"],["underline", pango.UNDERLINE_SINGLE]],
	"noteSpan": [],
}



inlineTags = {
	"<nl::noteLink>":1,
	"<nl::viewBlock>":2,
	"<nl::inlineTitle>":3,
	"<nl::viewItem>":4
}

"""
Plans:
Move all full lists of filters to seperate (searchable, probably by id) data structures. Keep temp list for display.
Move drawing to seperate methods
Rule/tag to take all text that matches real tags and make invisible
Rule to apply tags between pairs of tags. 
"""
class stateStore:
	tagBuf = None
	noteBuf = None
	tagMap = None
	
	#def __init__(self, id=-1, type=-1)
	#	noteBuf = gtk.TextBuffer(noteTag)
	#	tagBuf = gtk.TextBuffer(tagTab)
		
	def set_tagMap(newTagMap):
		tagMap = newTagMap
		
	def set_noteTags(newTagTab):
		tagTab = newTagTab
	
	#Don't forget about tag changes.u
	def gen_tagBuf(noteTags):
		tagBuf = gtk.TextBuffer(tagTab)
		for tag in noteTags:
			iter = tagBuf.get_end_iter()
			name = "tag" + str(tag)
			tagNF = "tagNF" + str(tag)
			self.tagBuf.insert_with_tags_by_name(iter, str(tagMap[tag][1]), name)
			iter = tagBuf.get_end_iter()
			tagBuf.insert_with_tags_by_name(iter, " [x]    ", tagNF, "red")
		
	
class NotesCore(gtk.Window):
	
	def __init__(self):
		super(NotesCore, self).__init__()
		self.connect("destroy", gtk.main_quit)
		self.set_title("NoteLink")
		self.set_size_request(900, 600)
		self.set_icon_from_file("note.png")
		self.set_position(gtk.WIN_POS_CENTER)
		self.stateNotebook = gtk.Notebook()
		self.readConf()
		self.focusCon = -1
		self.colors = [["white",0], ["red",1], ["green",2], ["blue",3], ["orange",4], ["purple",5], ["pink",6], ["yellow",7]]
		
		#Keyboard Shortcuts
		ag = gtk.AccelGroup()
		keys = gtk.accelerator_parse("<CTRL>b")
		ag.connect_group(keys[0], gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE, self.gotHere)
		self.add_accel_group(ag)
		
		#Main Application Panes
		mainPane = gtk.HBox(False,2)
		filterPane = gtk.VBox(False, 4)
		viewPane = gtk.VBox(False, 4)
		
		#List of expanded notes:
		self.expNotes = []
		
		#Filter Lists
		self.tagList = gtk.ListStore(str, int, str)
		self.viewList = gtk.ListStore(str, int)
		self.noteList = gtk.ListStore(str, int, str)
		self.loadFilters()
		self.tagView = gtk.TreeView()
		self.noteView = gtk.TreeView(self.noteList)
		self.viewView = gtk.TreeView(self.viewList)
		self.tagView.connect("cursor-changed", self.filter_row_changed, -1)
		self.viewView.connect("cursor-changed", self.filter_row_changed, -2)
		self.noteView.connect("cursor-changed", self.filter_row_changed, 0)
		self.switchState = True
		self.switch = True
		for label in self.searchTabs:
			cell = gtk.CellRendererText()
			col = gtk.TreeViewColumn(label)
			col.pack_start(cell, True)
			col.set_attributes(cell,text=0,id=1)
			if label == "Tags": 
				self.tagView.append_column(col)
				cell2 = gtk.CellRendererText()
				colCol = gtk.TreeViewColumn("Color")
				colCol.pack_start(cell2, True)
				colCol.set_attributes(cell2,background=2)
				self.tagView.append_column(colCol)
			elif label == "Views": self.viewView.append_column(col)
			elif label == "Notes": self.noteView.append_column(col)
		
		#Search Field
		self.searchField = gtk.Entry()
		self.searchField.set_size_request(245, 35)
		self.searchField.connect("key-release-event", self.filterInput)
		
		self.tagFilter = self.tagList.filter_new()
		self.tagFilter.set_visible_func(self.checkSort)
		self.viewFilter = self.viewList.filter_new()
		self.viewFilter.set_visible_func(self.checkSort)
		self.noteFilter = self.noteList.filter_new()
		self.noteFilter.set_visible_func(self.checkSort)
		self.tagView.set_model(self.tagFilter)
		self.viewView.set_model(self.viewFilter)
		self.noteView.set_model(self.noteFilter)
		
		#Formatting Buttons!
		
		#Create Filter Tabs
		self.filterNotebook = gtk.Notebook()
		for label in self.searchTabs:
			new = gtk.Button("New " + label.rstrip('s'))
			new.set_size_request(-1, 25)
			edit = gtk.Button("Edit " + label.rstrip('s'))
			edit.set_size_request(-1, 25)
			delete = gtk.Button("Delete " + label.rstrip('s'))
			delete.set_size_request(-1, 25)
			new.connect("clicked", self.ned_button_clicked, 0)
			edit.connect("clicked", self.ned_button_clicked, 0)
			delete.connect("clicked", self.ned_button_clicked, 0)
			cont = gtk.VBox(False,2)
			buttonBox = gtk.HBox(True, 0)
			buttonBox.pack_start(new)
			buttonBox.pack_start(edit)
			buttonBox.pack_start(delete)
			scrollPane = gtk.ScrolledWindow()
			if label == "Tags": scrollPane.add_with_viewport(self.tagView)
			elif label == "Views": scrollPane.add_with_viewport(self.viewView)
			elif label == "Notes": scrollPane.add_with_viewport(self.noteView)
			scrollPane.set_policy(gtk.POLICY_NEVER,gtk.POLICY_AUTOMATIC)
			scrollPane.set_shadow_type(gtk.SHADOW_NONE)
			scrollPane.child.set_shadow_type( gtk.SHADOW_NONE )
			cont.pack_start(scrollPane)
			cont.pack_start(buttonBox, False, False, 2)
			glabel = gtk.Label(label)
			self.filterNotebook.append_page(cont, glabel)
		filterPane.set_size_request(250, -1)
		filterPane.pack_start(self.searchField, False, False, 4)
		filterPane.pack_start(self.filterNotebook)
		
		#Tags
		self.toMarkup = {}
		self.noteTags = []
		self.viewTags = []
		self.tagTab = gtk.TextTagTable()
		for key in textTags.keys():
			tag = gtk.TextTag(textTags[key][0])
			for pair in textTags[key][1]:
				tag.set_property(pair[0],pair[1])
			self.tagTab.add(tag)
			self.toMarkup[tag] = key
		for tag in self.tagList:
			ttag = gtk.TextTag("tag" + str(tag[1]))
			tagNF = gtk.TextTag("tagNF" + str(tag[1]))
			tagP = gtk.TextTag("tagP" + str(tag[1]))
			color = gtk.gdk.Color(tag[2])
			total = color.red +  color.green + color.green
			ttag.set_property("background-gdk", color)
			tagNF.set_property("background", "white")
			tagNF.set_property("foreground", "red")
			tagNF.set_property("weight", 700)
			if total < 40000:
				ttag.set_property("foreground","white")
			self.tagTab.add(ttag)
			self.tagTab.add(tagNF)
			self.tagTab.add(tagP)
		for key in tagsNoMarkup.keys():
			tag = gtk.TextTag(key)
			for pair in tagsNoMarkup[key]:
				tag.set_property(pair[0],pair[1])
			self.tagTab.add(tag)
		for note in self.noteDict.keys():
			tag = gtk.TextTag("note" + str(note))
			self.tagTab.add(tag)
			self.noteTags.append(tag)
		for key in self.viewDict.keys():
			tag = gtk.TextTag("viewP" + str(key))
			self.tagTab.add(tag)
			self.viewTags.append(tag)
			tag2 = gtk.TextTag("viewLink" + str(key))
			self.tagTab.add(tag2)
			self.viewTags.append(tag2)
		
		#Create State Tabs
		self.stateNotebook.connect("switch-page", self.switchPage)
		self.stateNotebook.connect_after("switch-page", self.selectPage)
		self.newDefaultState()
		self.newState("+")
		
		viewPane.pack_start(self.stateNotebook, True, True, 1)
		mainPane.pack_start(filterPane, False, False, 1)
		mainPane.pack_start(viewPane, True, True, 1)
		
		self.add(mainPane)
		self.show_all()
		
	def set_stage(self):
		self.noteLayout = gtk.HBox()
		self.tagLayout = gtk.HBox()
		self.viewLayout = gtk.HBox()
		self.expNotes = []
		
		titleBox = gtk.HBox(False, 2)
		titLabel = gtk.Label()
		titLabel.set_markup('<span size="xx-large">Title:</span>')
		title = gtk.Entry()
		title.set_text(note[0])
		title.connect("focus-out-event", self.note_name_lose_focus, noteId)
		
		font = pango.FontDescription('Sans %s' % 18)
		self.stateNotebook.set_tab_label_text(self.stateNotebook.get_nth_page(self.stateNotebook.get_current_page()), note[0])
		self.red = gtk.ToggleButton()
		redImg = gtk.Image()
		redImg.set_from_file("img/red.png")
		self.red.set_image(redImg)
		self.red.set_size_request(-1, 25)
		self.red.set_property("can-focus", False)
		self.red.connect("toggled", self.format_button_toggled, "red")
		self.bold = gtk.ToggleButton()
		boldImg = gtk.Image()
		boldImg.set_from_file("img/bold.png")
		self.bold.set_image(boldImg)
		self.bold.set_size_request(-1, 25)
		self.bold.set_property("can-focus", False)
		self.bold.connect("toggled", self.format_button_toggled, "bold")
		self.ital = gtk.ToggleButton()
		italImg = gtk.Image()
		italImg.set_from_file("img/ital.png")
		self.ital.set_image(italImg)
		self.ital.set_size_request(-1, 25)
		self.ital.set_property("can-focus", False)
		self.ital.connect("toggled", self.format_button_toggled, "ital")
		self.titl = gtk.ToggleButton()
		titImg = gtk.Image()
		titImg.set_from_file("img/title.png")
		self.titl.set_image(titImg)
		self.titl.set_size_request(-1, 25)
		self.titl.set_property("can-focus", False)
		self.titl.connect("toggled", self.format_button_toggled, "title")
		tagLabel = gtk.Label()
		tagLabel.set_markup('<span size="x-large">Add Tag:</span>')
		textBuf = gtk.TextBuffer(self.tagTab)
		tagText = gtk.TextView(textBuf)
		tagText.set_wrap_mode(gtk.WRAP_WORD)
		tagText.connect("button-release-event", self.click_tag_text, noteId)
		tagText.set_cursor_visible(False)
		tagText.set_editable(False)
		for tag in self.noteDict[noteId][2]:
			iter = textBuf.get_end_iter()
			name = "tag" + str(tag)
			tagNF = "tagNF" + str(tag)
			textBuf.insert_with_tags_by_name(iter, str(self.tagMap[tag][1]), name)
			iter = textBuf.get_end_iter()
			textBuf.insert_with_tags_by_name(iter, " [x]    ", tagNF, "red")
		self.noteTagFilter = self.tagList.filter_new()
		tagEntry = gtk.Entry()
		tagDrop = gtk.EntryCompletion()
		tagDrop.set_model(self.noteTagFilter)
		tagDrop.set_text_column(0)
		tagDrop.connect("match-selected", self.add_tag_drop, noteId, tagText)
		tagDrop.set_inline_completion(True)
		tagDrop.set_inline_selection(True)
		tagDrop.set_match_func(self.filter_tags_by_text, [noteId, tagEntry])
		tagEntry.set_completion(tagDrop)
		tagEntry.connect("activate", self.add_tag_entry, noteId, tagText)
		self.noteTagFilter.set_visible_func(self.filter_existing_tags, [noteId, tagEntry])
		self.noteTagFilter.refilter()
		tagBox = gtk.HBox(False, 2)
		tagBox.pack_start(tagLabel, False, False, 0)
		tagBox.pack_start(tagEntry, False, False, 0)
		#tagBox.pack_start(tagAdd, False, False, 0)
		tagBox.pack_start(tagText, True, True, 1)
		title.modify_font(font)
		titleBox.pack_start(titLabel, False, 0, 0)
		titleBox.pack_start(title, True, True, 2)
		halign = gtk.Alignment(1, 0, 0, 0)
		new = gtk.Button("New Note")
		new.set_size_request(-1, 25)
		new.connect_after("clicked", self.new_note_button)
		close = gtk.Button("Close")
		close.set_size_request(-1, 25)
		close.connect_after("clicked", self.close_button)
		butBox = gtk.HBox()
		butBox.pack_start(new)
		butBox.pack_start(close)
		halign.add(butBox)
		titleBox.pack_start(halign)
		head.pack_start(titleBox, True, True, 3)
		head.pack_start(tagBox, False, False, 1)
		head.pack_start(gtk.HSeparator())
		head.show_all()
		self.expNotes.append(noteId)
		textBuf = self.buf_from_file("notes/" + self.noteDict[noteId][1])
		self.focusCon = textBuf.connect_after("insert-text", self.text_insert)
		text = gtk.TextView(textBuf)
		text.set_wrap_mode(gtk.WRAP_WORD)
		text.connect("focus-out-event", self.ViewFocusOut, noteId)
		text.connect_after("move-cursor", self.note_move_cursor_key, gtk.MOVEMENT_VISUAL_POSITIONS, 1)
		text.connect("button-release-event", self.note_move_cursor_mouse)
		scrollPane = gtk.ScrolledWindow()
		scrollPane.add_with_viewport(text)
		scrollPane.set_policy(gtk.POLICY_NEVER,gtk.POLICY_AUTOMATIC)
		scrollPane.set_shadow_type(gtk.SHADOW_NONE)
		scrollPane.child.set_shadow_type( gtk.SHADOW_NONE)
		insLbl = gtk.Label()
		insLbl.set_markup('<span size="x-large">   Insert:</span>')
		inNote = gtk.Button("Note")
		inNote.set_property("can-focus", False)
		inNote.set_size_request(-1, 25)
		inNote.connect_after("clicked", self.insert_note, text)
		inView= gtk.Button("View")
		inView.set_property("can-focus", False)
		inView.set_size_request(-1, 25)
		inView.connect_after("clicked", self.insert_view, text)
		formatRow = gtk.HBox()
		formatRow.pack_start(self.titl)
		formatRow.pack_start(self.red)
		formatRow.pack_start(self.bold)
		formatRow.pack_start(self.ital)
		formatRow.pack_start(insLbl)
		formatRow.pack_start(inNote, 2)
		formatRow.pack_start(inView, 2)
		rightAlign = gtk.Alignment()
		rightAlign = gtk.Alignment(1, 0, 0, 0)
		rightAlign.add(formatRow)
		body.pack_start(rightAlign, False, 1, 1)
		body.pack_start(gtk.HSeparator(), False, 1, 1)
		body.pack_start(scrollPane, True, True, 1)
		body.show_all()
		
	def ned_button_clicked(self, button, source):
		filterText = self.filterNotebook.get_tab_label_text(self.filterNotebook.get_nth_page(self.filterNotebook.get_current_page()))
		label = button.get_label()
		if label.find("Delete") != -1:
			if label.rfind("Tag") != -1: tree, rows = self.tagView.get_selection().get_selected_rows()
			if label.rfind("View") != -1: tree, rows = self.viewView.get_selection().get_selected_rows()
			if label.rfind("Note") != -1: tree, rows = self.noteView.get_selection().get_selected_rows()
			title = "Delete "
			if len(rows) == 1:
				iter = tree.get_iter(rows[0])
				id = tree.get_value(iter, 1)
				if label.rfind("Tag") != -1: title += "Tag : " + self.tagList2[id][0] 
				elif label.rfind("View") != -1: title += "View : " + self.viewDict[id] 
				elif label.rfind("Note") != -1: title += "Note : " + self.noteDict[id][0]
				viewDiag = gtk.Dialog(title, None, gtk.DIALOG_MODAL, (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT, gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
				confirm = gtk.Label()
				confirm.set_text("Are you sure?")
				confirm.show()
				viewDiag.vbox.pack_start(confirm)
				viewDiag.set_position(gtk.WIN_POS_CENTER)
				response = viewDiag.run()
				if response == gtk.RESPONSE_ACCEPT:
					conn = sqlite3.connect('notes.db')
					c = conn.cursor()
					if label.rfind("Tag") != -1:
						c.execute("DELETE from tagMap where tagId = %d" % id)
						c.execute("DELETE from tags where rowId = %d" % id)
						c.execute("DELETE from viewMap where type=0 and targetId=%d" % id)
						for noteId in self.tagMap[id][0]:
							self.noteDict[noteId][2].remove(id)
						self.tagMap.pop(id)
						self.tagList2.pop(id)
						self.tagView.get_model().get_model().remove(self.tagView.get_model().get_model().get_iter(rows[0]))
					elif label.rfind("Note") != -1:
						c.execute("DELETE from notes where rowId = %d" % id)
						c.execute("DELETE from tagMap where noteId = %d" % id)
						os.remove("notes/" + self.noteDict[id][1])
						self.noteDict.pop(id)
						self.noteView.get_model().get_model().remove(self.noteView.get_model().get_model().get_iter(rows[0]))
						for entry in self.tagMap.keys():
							if id in self.tagMap[entry][0]:
								self.tagMap[entry][0].remove(id)
					elif label.rfind("View") != -1:
						c.execute("DELETE from views where rowId = %d" % id)
						c.execute("DELETE from viewMap where viewId = %d" % id)
						c.execute("DELETE from viewMap where type=1 and targetId = %d" % id)
						self.viewView.get_model().get_model().remove(self.viewView.get_model().get_model().get_iter(rows[0]))
						self.viewMap.pop(id)
						self.viewDict.pop(id)
					self.filterInput(None, None)
					conn.commit()
					c.close()
					conn.close()
					page = self.stateNotebook.get_nth_page(self.stateNotebook.get_current_page())
					page.pageState = [-3, 0]
					self.renderState()
				viewDiag.destroy()
		else:
			if label.rfind("Tag") != -1:
				tree, rows = self.tagView.get_selection().get_selected_rows()
				tagDiag = gtk.Dialog("Edit Tag", None, gtk.DIALOG_MODAL, (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT, gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
				entry = gtk.Entry()
				tagDiag.set_position(gtk.WIN_POS_CENTER)
				######### CODE FOR PRESS ENTER CONFIRM
				#entry.connect("activate", responseToDialog, dialog, gtk.RESPONSE_OK)
				#########
				nameBox = gtk.HBox()
				nameBox.pack_start(gtk.Label("Tag Name:"), False, 5, 5)
				nameBox.pack_end(entry)
				colorLabel = gtk.Label()
				colorLabel.set_markup("Pick the tag color:")
				colorSwatch = gtk.ColorSelection()
				id = -1
				if label.find("Edit") != -1 and len(rows) == 1:
					tree, iter = self.tagView.get_selection().get_selected()
					id = self.tagView.get_model().get_value(iter, 1)
					entry.set_text(self.tagList2[id][0])
					color = gtk.gdk.Color(self.tagList2[id][1])
					colorSwatch.set_current_color(color)
				tagDiag.vbox.pack_start(nameBox, False, 4, 4)
				tagDiag.vbox.pack_start(colorLabel, False, 2, 2)
				tagDiag.vbox.pack_start(colorSwatch, False, 4, 4)
				tagDiag.show_all()
				response = tagDiag.run()
				text = entry.get_text()
				color = colorSwatch.get_current_color()
				if response == gtk.RESPONSE_ACCEPT:
					self.edit_tag(id, text, color.to_string())
				tagDiag.destroy()
			if label.rfind("View") != -1:
				tree, rows = self.viewView.get_selection().get_selected_rows()
				viewDiag = gtk.Dialog("Edit View", None, gtk.DIALOG_MODAL, (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT, gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
				viewDiag.set_position(gtk.WIN_POS_CENTER)
				entry = gtk.Entry()
				nameBox = gtk.HBox()
				nameBox.pack_start(gtk.Label("View Name:"), False, 5, 5)
				nameBox.pack_end(entry)
				listLabel = gtk.Label()
				listLabel.set_markup("Included tags and views:")
				#name, id, type, group
				incList = gtk.ListStore(str, int, int, str, int)
				incView = gtk.TreeView()
				incView.set_model(incList)
				cell = gtk.CellRendererText()
				col = gtk.TreeViewColumn("Entry")
				col.pack_start(cell, True)
				col.set_attributes(cell,text=0,id=1)
				incView.append_column(col)
				cell2 = gtk.CellRendererText()
				colCol = gtk.TreeViewColumn("AND")
				colCol.pack_start(cell2, True)
				colCol.set_attributes(cell2,background=3)
				incView.append_column(colCol)
				incView.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
				incView.set_size_request
				rem = gtk.Button()
				rem.set_label("Remove")
				rem.connect("clicked", self.view_rem_entry, incView)
				group = gtk.Button()
				group.set_label("Group")
				group.connect("clicked", self.view_group, incView)
				ungroup = gtk.Button()
				ungroup.set_label("Ungroup")
				ungroup.connect("clicked", self.view_ungroup, incView)
				incButBox = gtk.HBox()
				incButBox.pack_start(rem)
				incButBox.pack_start(group)
				incButBox.pack_start(ungroup)
				self.addTagFilter = self.tagList.filter_new()
				self.addTagFilter.set_visible_func(self.filter_added_view_tags, [incList, 0])
				self.addViewFilter = self.viewList.filter_new()
				self.addViewFilter.set_visible_func(self.filter_added_view_tags, [incList, 1])
				tagBox = gtk.HBox(False, 2)
				tagDrop= gtk.ComboBox()
				tagDrop.set_model(self.addTagFilter)
				cell = gtk.CellRendererText()
				tagDrop.pack_start(cell, True)
				tagDrop.set_attributes(cell, text=0, id=1)  
				tagAdd = gtk.Button()
				tagAdd.set_label("Add Tag")
				tagAdd.connect("clicked", self.view_add_entry, tagDrop, incList, 0)
				tagBox.pack_start(tagDrop)
				tagBox.pack_start(tagAdd)
				viewBox = gtk.HBox(False, 2)
				viewDrop= gtk.ComboBox()
				viewDrop.set_model(self.addViewFilter)
				cell = gtk.CellRendererText()
				viewDrop.pack_start(cell, True)
				viewDrop.set_attributes(cell, text=0, id=1)  
				viewAdd = gtk.Button()
				viewAdd.set_label("Add View")
				viewAdd.connect("clicked", self.view_add_entry, viewDrop, incList, 1)
				viewBox.pack_start(viewDrop)
				viewBox.pack_start(viewAdd)
				
				viewDiag.vbox.pack_start(nameBox, False, 4, 4)
				viewDiag.vbox.pack_start(gtk.HSeparator(), True, True, 20)
				viewDiag.vbox.pack_start(listLabel, False, 2, 2)
				viewDiag.vbox.pack_start(incView, False, 2, 2)
				viewDiag.vbox.pack_start(incButBox, False, 2, 2)
				viewDiag.vbox.pack_start(gtk.HSeparator(), True, True, 20)
				viewDiag.vbox.pack_start(tagBox, False, 2, 2)
				viewDiag.vbox.pack_start(viewBox, False, 2, 2)
				viewDiag.vbox.show_all()
				
				id = -1
				if label.find("Edit") != -1 and len(rows) == 1:
					tree, iter = self.viewView.get_selection().get_selected()
					id = self.viewView.get_model().get_value(iter, 1)
					entry.set_text(self.viewDict[id])
					entries = self.viewMap[id]
					for item in entries:
						name = self.viewDict[item[2]] if item[0] == 1 else self.tagList2[item[2]][0]
						incList.append([name, item[2], item[0], self.colors[item[1]][0], item[1]])
				response = viewDiag.run()
				name = entry.get_text()
				if response == gtk.RESPONSE_ACCEPT:
					self.edit_view(id, name, incList)
				viewDiag.destroy()
			if label.rfind("Note") != -1:
				newId = self.new_note()
				self.stateNotebook.get_nth_page(self.stateNotebook.get_current_page()).pageState = [ 0, newId]
				self.renderState()
				
	def close_button(self, button):
		if self.stateNotebook.get_n_pages() > 2:
			self.stateNotebook.remove_page(self.stateNotebook.get_current_page())
		else:
			self.stateNotebook.get_nth_page(self.stateNotebook.get_current_page()).pageState = [-3,0]
			self.renderState()
		
	def edit_view(self, id, name, incList):
		conn = sqlite3.connect('notes.db')
		c = conn.cursor()
		if id == -1:
			sql = "insert into views (name) values ('" + name + "');"
			c.execute(sql)
			id = c.lastrowid
			self.viewList.append([name, id])
			self.viewDict[id] = name
		else:
			sql = "update views set name='" + name + "' where rowid=" + str(id) + ";"
			c.execute(sql)
			self.viewDict[id] = [name]
			for i in range(0, len(self.viewList)):
				if self.viewList[i][1] == id:
					self.viewList[i][0] = name
		print "VIEW ID: %d" % id
		sql = "delete from viewMap where viewId = %d;" % id
		c.execute(sql)
		conn.commit()
		#type, group, id
		self.viewMap[id] = []
		for entry in incList:
			sql = "insert into viewMap values (%d, %d, %d, %d);" % (id, entry[2], entry[4], entry[1])
			print "SQL: %s" % sql
			print entry
			c.execute(sql)
			self.viewMap[id].append([entry[2], entry[4], entry[1]])
		conn.commit()
		c.close()
		conn.close()
		self.viewFilter.refilter()
		
	def edit_tag(self, id, text, color):
		conn = sqlite3.connect('notes.db')
		c = conn.cursor()
		if id == -1:
			sql = "insert into tags (name, color) values ('" + text + "', '" + color + "');"
			c.execute(sql)
			newId = c.lastrowid
			self.tagList2[newId] = [text, color]
			self.tagList.append([text, newId, color])
		else:
			sql = "update tags set name='" + text + "', color='" + color + "' where rowid=" + str(id) + ";"
			c.execute(sql)
			self.tagList2[id] = [text, color]
			for i in range(0, len(self.tagList)):
				if self.tagList[i][1] == id:
					self.tagList[i][0] = text
					self.tagList[i][2] = color
		conn.commit()
		c.close()
		conn.close()
		self.tagFilter.refilter()
		
	def filter_added_view_tags(self, model, iter, vars):
		for row in vars[0]:
			print str(model.get(iter, 1))
			print "%s-%s-%s" % (str(row[0]),str(row[1]),str(row[2]))
			if model.get(iter, 1)[0] == row[1]:
				print "%s:%s" % (model.get(iter, 0), row[0])
				if model.get(iter, 0)[0] == row[0]: return False
		return True
		
	def view_group(self, button, incView):
		model, active = incView.get_selection().get_selected_rows()
		if len(active) < 0:
			return None
		color = self.colors[1]
		self.colors.remove(color)
		for path in active:
			model.set(model.get_iter(path), 3, color[0], 4, color[1])
		
	def view_rem_entry(self, button, incView):
		model, active = incView.get_selection().get_selected_rows()
		if len(active) < 0:
			return None
		for path in active:
			iter = model.get_iter(path)
			self.colors.append([model.get(iter, 3)[0], model.get(iter, 4)[0]])
			model.remove(model.get_iter(path))
		self.colors = list(set(self.colors))
		print self.colors
		self.addTagFilter.refilter()
		self.addTagFilter.refilter()
		
	def view_ungroup(self, button, incView):
		model, active = incView.get_selection().get_selected_rows()
		if len(active) < 0:
			return None
		for path in active:
			iter = model.get_iter(path)
			self.colors.append([model.get(iter, 3)[0], model.get(iter, 4)[0]])
			model.set(model.get_iter(path), 3, "white")
			model.set(model.get_iter(path), 4, 0)
		self.colors = list(set(self.colors))
		
	def view_add_entry(self, button, drop, incList, type):
		model = drop.get_model()
		active = drop.get_active()
		if active < 0:
			return None
		id = model[active][1]
		name = model[active][0]
		incList.append([name, id, type, "white", 0])
		drop.get_model().refilter()
		
	def readConf(self):
		conf = ConfigParser.ConfigParser()
		conf.read('notes.cfg')
		self.searchTabs = eval(conf.get("config", "searchTabs"), {}, {})
		if conf.get("progState", "restore") == "true":
			for i in [ entry[1] for entry in conf.items("progState") if entry[0].startswith("viewState")]:
				self.newState(i[2], i[1], i[0])
		else:
			self.newState("Search", -1, 0)
		
	def switchPage(self, notebook, temp, page_num):
		page = notebook.get_nth_page(page_num)
		if notebook.get_tab_label(page).get_text() == "+":
			self.newDefaultState()
			self.switch = False
		else:
			print "Other" + str(page_num)
			
	def gotHere1(self, a):
		self.gotHere()
	
	def gotHere2(self, a, b):
		self.gotHere()
		
	def gotHere3(self, a, b, c):
		self.gotHere()
		
	def gotHere(self):
		print "########## GOT HERE ##########"
		
	def selectPage(self, notebook, temp, page_num):
		print "Yoyo"
		print notebook.get_tab_label(notebook.get_nth_page(notebook.get_current_page())).get_text() 
		if notebook.get_tab_label(notebook.get_nth_page(notebook.get_current_page())).get_text() == "+":
			self.stateNotebook.prev_page()
		self.renderState()
		
	def loadFilters(self):
		self.noteDict = {}
		self.tagMap = {}
		self.viewMap = {}
		self.viewDict = {}
		self.tagList2 = {}
		conn = sqlite3.connect('notes.db')
		c = conn.cursor()
		
		c.execute('''SELECT name, ROWID, color from tags;''')
		for row in c:
			self.tagList.append([row[0], row[1], row[2]])
			self.tagList2[row[1]] = [row[0], row[2]]
			self.tagMap[row[1]] = [[], row[0]]
		
		c.execute('''select name, ROWID from views;''')
		for row in c:
			self.viewList.append([row[0], row[1]])
			self.viewDict[row[1]] = row[0]
		
		c.execute('''select title, ROWID, file from notes;''')
		for row in c:
			self.noteList.append([row[0], row[1], row[2]])
			self.noteDict[row[1]] = [row[0], row[2], []]
			
		for note in self.noteList:
			searchString = "SELECT tagId from tagMap where noteId =" + str(note[1])
			c.execute(searchString)
			for row in c:
				self.noteDict[note[1]][2].append(row[0]) 
		
		c.execute('''select tags.ROWID, tagMap.noteId, tags.name from tagMap inner join tags on tagMap.tagId=tags.ROWID;''')
		for row in c:
			self.tagMap[row[0]][0].append(row[1])
		
		c.execute('''SELECT * from viewMap;''')
		for row in c:
			#viewId, type (tag=0, view=1), group, id
			if row[0] in self.viewMap:
				self.viewMap[row[0]].append([row[1], row[2], row[3]])
			else:
				self.viewMap[row[0]] =[[row[1], row[2], row[3]]]
		c.close()
		
	def filter_row_changed(self, treeview, state):
		print state
		self.clickFilter(treeview, treeview.get_model().get_path((treeview.get_selection().get_selected()[1])), None, state)
		
	def clickFilter(self, treeview, path, view_column, state):
		print "clickFilter"
		page = self.stateNotebook.get_nth_page(self.stateNotebook.get_current_page())
		id = treeview.get_model().get_value(treeview.get_model().get_iter(path), 1)
		name = treeview.get_model().get_value(treeview.get_model().get_iter(path), 0)
		stateText = self.filterNotebook.get_tab_label_text(self.filterNotebook.get_nth_page(self.filterNotebook.get_current_page()))
		tabText = ""
		if state == -1:
			tabText = "Tag: " + self.tagList2[id][0]
		elif state == -2:
			tabText = "View: " + name 
		elif state == 0:
			print "Note, you fuckers."
		self.stateNotebook.set_tab_label_text(page, tabText)
		page.pageState = [state, id] 
		self.renderState()
		
	def new_note_button(self, button):
		print "new_note_button"
		newId = self.new_note()
		self.stateNotebook.get_nth_page(self.stateNotebook.get_current_page()).pageState = [ 0, newId]
		self.renderState()
		
	def new_note(self):
		conn = sqlite3.connect('notes.db')
		c = conn.cursor()
		file = "%d.nl" % (time.time()*100)
		print file
		sql = "insert into notes (title, file) values ('', '" + file + "');"
		c.execute(sql)
		newId = c.lastrowid
		conn.commit()
		c.close()
		conn.close()
		self.noteList.append(["", newId, file])
		self.noteDict[newId] = ["", file, []]
		fileOut = open("notes/" + file, "w")
		fileOut.write("")
		return newId
		
	def note_name_lose_focus(self, noteField, event, noteId):
		noteName = noteField.get_text()
		self.stateNotebook.set_tab_label_text(self.stateNotebook.get_nth_page(self.stateNotebook.get_current_page()), noteName)
		self.set_note_name(noteId, noteName)
		for note in self.noteList:
			if note[1] == noteId:
				note[0] = noteName
		self.noteDict[noteId] = [noteName, self.noteDict[noteId][1], self.noteDict[noteId][2]]
		
	def set_note_name(self, noteId, noteName):
		conn = sqlite3.connect('notes.db')
		c = conn.cursor()
		sql = "update notes set title='" + noteName + "' where ROWID=" + str(noteId) + ";"
		c.execute(sql)
		conn.commit()
		c.close()
		conn.close()
		
	def newState(self, title):
		cont = gtk.VBox(False, 2)
		head = gtk.VBox(False, 2)
		body = gtk.VBox(False, 2)
		body.cname = "body"
		head.cname = "header"
		cont.pack_start(head, False, False, 2)
		cont.pack_start(body)
		cont.pageState = [-3, 0]
		cont.show()
		glabel = gtk.Label()
		glabel.set_markup(title)
		glabel.show()
		insPos = self.stateNotebook.get_n_pages()-1 if self.stateNotebook.get_n_pages() > 1 else self.stateNotebook.get_n_pages()
		self.stateNotebook.insert_page(cont, glabel, insPos) 
		if title != "+":
			self.renderState()
		
	def clickedNoteRight(self, widget, event, noteId):
		"Clicked Note Field"
		page2 = self.stateNotebook.get_nth_page(self.stateNotebook.get_current_page())
		page2.pageState = [0, noteId]
		
	def focusCallRender(self, widget, event):
		self.renderState()
		
	def popdownList(self, widget, event):
		print "&&&&&&&&&&&&############"
		widget.popup()
		
	def renderState(self):
		print "Rendering"
		page = self.stateNotebook.get_nth_page(self.stateNotebook.get_current_page())
		state = page.pageState[0]
		print "State:" + str(state)
		head = page.get_children()[0]
		body = page.get_children()[1]
		for child in head.children(): head.remove(child)
		for child in body.children(): body.remove(child)
		id = page.pageState[1]
		if state == -3:
			self.renderBlankState(body, head)
		elif state == -2: 
			self.renderViewState(body, head, id)
		elif state == -1: 
			self.renderTagState(body, head, id)
		elif state == 0:
			self.renderNoteState(body, head, id)
		
	def renderTagState(self, body, head, tagId):
		print tagId
		print self.tagMap
		print self.tagMap[tagId]
		print self.tagList2
		noteIds = self.tagMap[tagId][0]
		glabel = gtk.Label()
		glabel.set_markup('<span size = "100">Tag: ' + self.tagList2[tagId][0] +'</span>')
		glabel.show()
		self.stateNotebook.set_tab_label_text(self.stateNotebook.get_nth_page(self.stateNotebook.get_current_page()), "Tag: " + self.tagList2[tagId][0])
		head.pack_start(glabel, False)
		scrollPane = self.list_tag_notes_clickable(noteIds)
		body.pack_start(scrollPane)

			
	def list_tag_notes_clickable(self, noteIds):
		scrollPane = gtk.ScrolledWindow()
		listNotes = gtk.VBox()
		scrollPane.set_border_width(10)
		scrollPane.show()
		valign = gtk.Alignment(0, 0, 1, 0)
		valign.add(listNotes)
		scrollPane.add_with_viewport(valign)
		scrollPane.set_policy(gtk.POLICY_NEVER,gtk.POLICY_AUTOMATIC)
		scrollPane.set_shadow_type(gtk.SHADOW_NONE)
		scrollPane.child.set_shadow_type( gtk.SHADOW_NONE )
		col = gtk.gdk.color_parse("#FFFFFF")
		scrollPane.modify_bg(gtk.STATE_NORMAL, col)
		listNotes.modify_bg(gtk.STATE_NORMAL, col)
		valign.show()
		listNotes.show()
		for i in range(0, len(noteIds)):
			noteDesc = gtk.TextView()
			noteDesc.set_editable(False)
			noteDesc.set_cursor_visible(False)
			noteDesc.set_border_window_size(gtk.TEXT_WINDOW_TOP,10)
			noteDesc.set_wrap_mode(gtk.WRAP_WORD)
			noteDesc.connect("focus-in-event", self.clickedNoteRight, noteIds[i])
			noteDesc.connect_after("focus-in-event", self.focusCallRender)
			textBuf = gtk.TextBuffer(self.tagTab)
			iter = textBuf.get_end_iter()
			textBuf.insert_with_tags_by_name(iter, self.noteDict[noteIds[i]][0] + "\n", "title")
			iter = textBuf.get_end_iter()
			textBuf.insert(iter,"\n")
			print self.tagTab
			for tag in self.noteDict[noteIds[i]][2]:
				iter = textBuf.get_end_iter()
				name = "tag" + str(tag)
				textBuf.insert_with_tags_by_name(iter, str(self.tagMap[tag][1]), name)
				iter = textBuf.get_end_iter()
				textBuf.insert(iter, ", ")
			noteDesc.set_buffer(textBuf)
			noteDesc.show()
			listNotes.pack_start(noteDesc, False, False, 0)
		return scrollPane
		
	def renderNoteState(self, body, head, noteId):
		self.expNotes = []
		note = self.noteDict[noteId]
		titleBox = gtk.HBox(False, 2)
		titLabel = gtk.Label()
		titLabel.set_markup('<span size="xx-large">Title:</span>')
		title = gtk.Entry()
		title.set_text(note[0])
		title.connect("focus-out-event", self.note_name_lose_focus, noteId)
		font = pango.FontDescription('Sans %s' % 18)
		self.stateNotebook.set_tab_label_text(self.stateNotebook.get_nth_page(self.stateNotebook.get_current_page()), note[0])
		self.red = gtk.ToggleButton()
		redImg = gtk.Image()
		redImg.set_from_file("img/red.png")
		self.red.set_image(redImg)
		self.red.set_size_request(-1, 25)
		self.red.set_property("can-focus", False)
		self.red.connect("toggled", self.format_button_toggled, "red")
		self.bold = gtk.ToggleButton()
		boldImg = gtk.Image()
		boldImg.set_from_file("img/bold.png")
		self.bold.set_image(boldImg)
		self.bold.set_size_request(-1, 25)
		self.bold.set_property("can-focus", False)
		self.bold.connect("toggled", self.format_button_toggled, "bold")
		self.ital = gtk.ToggleButton()
		italImg = gtk.Image()
		italImg.set_from_file("img/ital.png")
		self.ital.set_image(italImg)
		self.ital.set_size_request(-1, 25)
		self.ital.set_property("can-focus", False)
		self.ital.connect("toggled", self.format_button_toggled, "ital")
		self.titl = gtk.ToggleButton()
		titImg = gtk.Image()
		titImg.set_from_file("img/title.png")
		self.titl.set_image(titImg)
		self.titl.set_size_request(-1, 25)
		self.titl.set_property("can-focus", False)
		self.titl.connect("toggled", self.format_button_toggled, "title")
		tagLabel = gtk.Label()
		tagLabel.set_markup('<span size="x-large">Add Tag:</span>')
		textBuf = gtk.TextBuffer(self.tagTab)
		tagText = gtk.TextView(textBuf)
		tagText.set_wrap_mode(gtk.WRAP_WORD)
		tagText.connect("button-release-event", self.click_tag_text, noteId)
		tagText.set_cursor_visible(False)
		tagText.set_editable(False)
		for tag in self.noteDict[noteId][2]:
			iter = textBuf.get_end_iter()
			name = "tag" + str(tag)
			tagNF = "tagNF" + str(tag)
			textBuf.insert_with_tags_by_name(iter, str(self.tagMap[tag][1]), name)
			iter = textBuf.get_end_iter()
			textBuf.insert_with_tags_by_name(iter, " [x]    ", tagNF, "red")
		self.noteTagFilter = self.tagList.filter_new()
		tagEntry = gtk.Entry()
		tagDrop = gtk.EntryCompletion()
		tagDrop.set_model(self.noteTagFilter)
		tagDrop.set_text_column(0)
		tagDrop.connect("match-selected", self.add_tag_drop, noteId, tagText)
		tagDrop.set_inline_completion(True)
		tagDrop.set_inline_selection(True)
		tagDrop.set_match_func(self.filter_tags_by_text, [noteId, tagEntry])
		tagEntry.set_completion(tagDrop)
		tagEntry.connect("activate", self.add_tag_entry, noteId, tagText)
		self.noteTagFilter.set_visible_func(self.filter_existing_tags, [noteId, tagEntry])
		self.noteTagFilter.refilter()
		tagBox = gtk.HBox(False, 2)
		tagBox.pack_start(tagLabel, False, False, 0)
		tagBox.pack_start(tagEntry, False, False, 0)
		#tagBox.pack_start(tagAdd, False, False, 0)
		tagBox.pack_start(tagText, True, True, 1)
		title.modify_font(font)
		titleBox.pack_start(titLabel, False, 0, 0)
		titleBox.pack_start(title, True, True, 2)
		halign = gtk.Alignment(1, 0, 0, 0)
		new = gtk.Button("New Note")
		new.set_size_request(-1, 25)
		new.connect_after("clicked", self.new_note_button)
		close = gtk.Button("Close")
		close.set_size_request(-1, 25)
		close.connect_after("clicked", self.close_button)
		butBox = gtk.HBox()
		butBox.pack_start(new)
		butBox.pack_start(close)
		halign.add(butBox)
		titleBox.pack_start(halign)
		head.pack_start(titleBox, True, True, 3)
		head.pack_start(tagBox, False, False, 1)
		head.pack_start(gtk.HSeparator())
		head.show_all()
		self.expNotes.append(noteId)
		textBuf = self.buf_from_file("notes/" + self.noteDict[noteId][1])
		self.focusCon = textBuf.connect_after("insert-text", self.text_insert)
		text = gtk.TextView(textBuf)
		text.set_wrap_mode(gtk.WRAP_WORD)
		text.connect("focus-out-event", self.ViewFocusOut, noteId)
		text.connect_after("move-cursor", self.note_move_cursor_key, gtk.MOVEMENT_VISUAL_POSITIONS, 1)
		text.connect("button-release-event", self.note_move_cursor_mouse)
		scrollPane = gtk.ScrolledWindow()
		scrollPane.add_with_viewport(text)
		scrollPane.set_policy(gtk.POLICY_NEVER,gtk.POLICY_AUTOMATIC)
		scrollPane.set_shadow_type(gtk.SHADOW_NONE)
		scrollPane.child.set_shadow_type( gtk.SHADOW_NONE)
		insLbl = gtk.Label()
		insLbl.set_markup('<span size="x-large">   Insert:</span>')
		inNote = gtk.Button("Note")
		inNote.set_property("can-focus", False)
		inNote.set_size_request(-1, 25)
		inNote.connect_after("clicked", self.insert_note, text)
		inView= gtk.Button("View")
		inView.set_property("can-focus", False)
		inView.set_size_request(-1, 25)
		inView.connect_after("clicked", self.insert_view, text)
		formatRow = gtk.HBox()
		formatRow.pack_start(self.titl)
		formatRow.pack_start(self.red)
		formatRow.pack_start(self.bold)
		formatRow.pack_start(self.ital)
		formatRow.pack_start(insLbl)
		formatRow.pack_start(inNote, 2)
		formatRow.pack_start(inView, 2)
		rightAlign = gtk.Alignment()
		rightAlign = gtk.Alignment(1, 0, 0, 0)
		rightAlign.add(formatRow)
		body.pack_start(rightAlign, False, 1, 1)
		body.pack_start(gtk.HSeparator(), False, 1, 1)
		body.pack_start(scrollPane, True, True, 1)
		body.show_all()
		
	def hotkey_input(self, accelgroup, acceleratable, accel_key, accel_mods):
		print "Hit Hotkey!"
		print accel_key
		
	def insert_note(self, button, textView):
		tagDiag = gtk.Dialog("Insert Note", None, gtk.DIALOG_MODAL, (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT, gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
		textBuf = textView.get_buffer()
		textBuf.disconnect(self.focusCon)
		pos = textBuf.get_property('cursor-position')
		tagDrop = gtk.ComboBox()
		tagDrop.set_model(self.noteList)
		tagDiag.set_position(gtk.WIN_POS_CENTER)
		cell = gtk.CellRendererText()
		tagDrop.pack_start(cell, True)
		tagDrop.set_attributes(cell, text=0, id=1)  
		tagDiag.vbox.pack_start(tagDrop)
		tagDiag.vbox.show_all()
		tagDrop.show()
		mark = textBuf.create_mark("insPos", textBuf.get_iter_at_offset(pos), True)
		response = tagDiag.run()
		if response == gtk.RESPONSE_ACCEPT:
			model = tagDrop.get_model()
			active = tagDrop.get_active()
			if active < 0:
				return None
			noteId = model[active][1]
			textBuf.insert(textBuf.get_iter_at_mark(mark), "\n")
			textBuf.insert_with_tags_by_name(textBuf.get_iter_at_mark(mark), "<nl::noteLink>%d,0</nl::noteLink>" % noteId, "invisible")
			textBuf.insert_with_tags_by_name(textBuf.get_iter_at_mark(mark), "  [x]", "delMark")
			textBuf.insert_with_tags_by_name(textBuf.get_iter_at_mark(mark), " [+]", "expandMark")
			textBuf.insert_with_tags_by_name(textBuf.get_iter_at_mark(mark), self.noteDict[noteId][0], "noteLink")
			if not textBuf.get_iter_at_mark(mark).starts_line():
				textBuf.insert(textBuf.get_iter_at_mark(mark), "\n")
		tagDiag.destroy()
		self.focusCon = textBuf.connect_after("insert-text", self.text_insert)
		
	def insert_view(self, button, textView):
		viewDiag = gtk.Dialog("Insert View", None, gtk.DIALOG_MODAL, (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT, gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
		textBuf = textView.get_buffer()
		textBuf.disconnect(self.focusCon)
		pos = textBuf.get_property('cursor-position')
		viewDrop= gtk.ComboBox()
		viewDrop.set_model(self.viewList)
		viewDiag.set_position(gtk.WIN_POS_CENTER)
		cell = gtk.CellRendererText()
		viewDrop.pack_start(cell, True)
		viewDrop.set_attributes(cell, text=0, id=1)  
		viewDiag.vbox.pack_start(viewDrop)
		viewDiag.vbox.show_all()
		viewDrop.show()
		response = viewDiag.run()
		startMark = textBuf.create_mark("startMark", textBuf.get_iter_at_offset(pos-1), False)
		if response == gtk.RESPONSE_ACCEPT:
			model = viewDrop.get_model()
			active = viewDrop.get_active()
			if active < 0:
				return None
			viewId = model[active][1]
			holdMark = textBuf.create_mark("hold", textBuf.get_iter_at_offset(pos), False)
			textBuf.insert_with_tags_by_name(textBuf.get_iter_at_mark(holdMark), self.viewDict[viewId], "viewTitle", "viewP"+str(viewId))
			textBuf.insert_with_tags_by_name(textBuf.get_iter_at_mark(holdMark), "  [x]\n", "delMark")
			for row in self.viewMap[viewId]:
				iter = textBuf.get_iter_at_mark(holdMark)
				if row[0] == 0:
					name = self.tagList2[row[2]][0]
					tag = "tagP" + str(row[2])
				else:
					name = self.viewDict[row[2]]
					tag = "viewP" + str(row[2])
				textBuf.insert_with_tags(iter, name + "\n", self.tagTab.lookup(tag), self.tagTab.lookup("link"))
			iter = textBuf.get_iter_at_mark(holdMark)
			iter.backward_char()
			iter2 = textBuf.get_iter_at_mark(startMark)
			iter2.forward_char()
			textBuf.apply_tag(self.tagTab.lookup("viewLink"+str(viewId)), iter2, iter)
		viewDiag.destroy()
		self.focusCon = textBuf.connect_after("insert-text", self.text_insert)
		
	def filter_existing_tags(self, model, iter, params):
		noteId = params[0]
		tagDrop = params[1]
		id = model.get_value(iter, 1)
		if id not in self.noteDict[noteId][2]:
			if tagDrop.get_text():
				if len(tagDrop.get_text()) == 0:
					return True
				search = tagDrop.get_text()
				value = model.get_value(iter, 0)
				return value.lower().find(search.lower()) != -1
			else:
				return True
		return False
		
	def filter_tags_by_text(self, completion, key_string, iter, params):
		return self.filter_existing_tags(completion.get_model(), iter, params)
	
	def add_tag_drop(self, completion, model, iter, noteId, entry, text):
		tagId = model.get_value(iter, 1)
		self.add_tag(model, tagId, noteId, entry, text)
		
	def add_tag_entry(self, entry, noteId, text):
		self.noteTagFilter.refilter()
		tagModel = entry.get_completion().get_model()
		iter = tagModel.get_iter_root()
		tagId = tagModel.get_value(iter, 1)
		self.add_tag(tagModel, tagId, noteId, entry, text)
		
	def add_tag(self, model, tagId, noteId, entry, text):
		self.noteDict[noteId][2].append(tagId)
		self.tagMap[tagId][0].append(noteId)
		textBuf = text.get_buffer()
		iter = textBuf.get_end_iter()
		name = "tag" + str(tagId)
		tagNF = "tagNF" + str(tagId)
		textBuf.insert_with_tags_by_name(iter, str(self.tagMap[tagId][1]), name)
		iter = textBuf.get_end_iter()
		textBuf.insert_with_tags_by_name(iter, " [x]    ", tagNF)
		
		entry.set_text("")
		self.noteTagFilter.refilter()
		
		conn = sqlite3.connect('notes.db')
		c = conn.cursor()
		sql = "insert into tagMap (noteId, tagId) values (%d, %d)" % (noteId, tagId)
		c.execute(sql)
		conn.commit()
		c.close()
		conn.close()
		
	def click_tag_text(self, textView, event, noteId):
		buf = textView.get_buffer()
		conn = sqlite3.connect('notes.db')
		c = conn.cursor()
		iter = buf.get_iter_at_offset(buf.get_property('cursor-position'))
		for tag in iter.get_tags():
			name = tag.get_property("name")
			if name.find("tagNF") == 0:
				id = int(re.search('[0-9]+', name).group(0))
				tag2 = self.tagTab.lookup("tag" + str(id))
				iter2 = iter.copy()
				iter2.forward_to_tag_toggle(tag)
				while not iter.begins_tag(tag2) and not iter.starts_line():
					iter.backward_to_tag_toggle(tag2)
				self.noteDict[noteId][2].remove(id)
				self.tagMap[id][0].remove(noteId)
				buf.delete(iter, iter2)
				sql = "delete from tagMap where noteId=%d and tagId=%d" % (noteId, id)
				c.execute(sql)
				conn.commit()
		self.noteTagFilter.refilter()
		c.close()
		conn.close()
		print "Clicked note: %d" % (noteId)
		
	def buf_from_file(self, filename):
		noteFile = open(filename, "r")
		textBuf = gtk.TextBuffer(self.tagTab)
		textBuf.set_text(noteFile.read())
		print textTags
		for key in textTags.keys():
			start = textBuf.get_start_iter()
			close = textBuf.get_start_iter()
			closeTag = key.replace("<", "</")
			while 1==1:
				startPos = start.forward_search(key, gtk.TEXT_SEARCH_TEXT_ONLY)
				if startPos == None:
					break
				closePos = close.forward_search(closeTag, gtk.TEXT_SEARCH_TEXT_ONLY)
				startMark1 = textBuf.create_mark("start1", startPos[0], False)
				startMark2 = textBuf.create_mark("start2", startPos[1], False)
				closeMark1 = textBuf.create_mark("end1", closePos[0], False)
				closeMark2 = textBuf.create_mark("end2", closePos[1], True)
				if key not in inlineTags:
					textBuf.apply_tag_by_name(textTags[key][0],startPos[1],closePos[0])
					textBuf.delete(startPos[0],startPos[1])
					closePos = [textBuf.get_iter_at_mark(closeMark1), textBuf.get_iter_at_mark(closeMark2)]
					textBuf.delete(closePos[0],closePos[1])
				if key == "<nl::noteLink>":
					text = textBuf.get_text(textBuf.get_iter_at_mark(startMark2),textBuf.get_iter_at_mark(closeMark1)).split(",")
					noteId = int(text[0])
					expand = int(text[1])
					expand = expand if noteId not in self.expNotes else 0
					noteName = self.noteDict[noteId][0]
					iter = closePos[1].copy()
					#iter.forward_char()
					#textBuf.remove_all_tags(textBuf.get_iter_at_mark(startMark1), iter)
					textBuf.apply_tag(self.tagTab.lookup("invisible"), textBuf.get_iter_at_mark(startMark1), textBuf.get_iter_at_mark(closeMark2))
					expandText = [" [+]","expandMark"] if expand == 0 else [" [-]","shrinkMark"]
					textBuf.insert_with_tags_by_name(textBuf.get_iter_at_mark(startMark1), noteName, "noteLink")
					textBuf.insert_with_tags_by_name(textBuf.get_iter_at_mark(startMark1), expandText[0], expandText[1])
					textBuf.insert_with_tags_by_name(textBuf.get_iter_at_mark(startMark1), "  [x]", "delMark")
					final = textBuf.get_iter_at_mark(closeMark2)
					iter = textBuf.get_iter_at_mark(startMark1)
					iter.set_line_offset(0)
					begin = textBuf.create_mark("begin", iter, True)
					if expand == 1:
						self.expNotes.append(noteId)
						inBuf = self.buf_from_file("notes/" + self.noteDict[noteId][1])
						iter = textBuf.get_iter_at_mark(closeMark2)
						iter.forward_char()
						noteMark = textBuf.create_mark("note", iter, True)
						final = textBuf.get_iter_at_mark(self.insert_note_buf(textBuf, inBuf, noteMark, noteId))
					#print "NoteSpan: %s" % textBuf.get_text(final, textBuf.get_iter_at_mark(begin))
					#textBuf.apply_tag(self.tagTab.lookup("noteSpan"), final, textBuf.get_iter_at_mark(begin))
				if key == "<nl::viewLink>":
					viewId = int(textBuf.get_text(textBuf.get_iter_at_mark(startMark2),textBuf.get_iter_at_mark(closeMark1)))
					name = self.viewDict[viewId]
					iter = closePos[1].copy()
					textBuf.delete(textBuf.get_iter_at_mark(startMark1), textBuf.get_iter_at_mark(closeMark2))
					iter =  textBuf.get_iter_at_mark(closeMark2)
					iter.forward_char()
					holdMark = textBuf.create_mark("hold", iter, False)
					textBuf.insert_with_tags_by_name(textBuf.get_iter_at_mark(holdMark), self.viewDict[viewId], "viewTitle", "viewP"+str(viewId))
					textBuf.insert_with_tags_by_name(textBuf.get_iter_at_mark(holdMark), "  [x]\n", "delMark")
					for row in self.viewMap[viewId]:
						iter = textBuf.get_iter_at_mark(holdMark)
						if row[0] == 0:
							name = self.tagList2[row[2]][0]
							tag = "tagP" + str(row[2])
						else:
							name = self.viewDict[row[2]]
							tag = "viewP" + str(row[2])
						textBuf.insert_with_tags(iter, name + "\n", self.tagTab.lookup(tag), self.tagTab.lookup("link"))
					print "Text With Tag: %s" % textBuf.get_text(textBuf.get_iter_at_mark(startMark1), textBuf.get_iter_at_mark(holdMark))
					iter = textBuf.get_iter_at_mark(holdMark)
					iter.backward_char()
					textBuf.apply_tag(self.tagTab.lookup("viewLink"+str(viewId)), textBuf.get_iter_at_mark(startMark1), iter)
				start = textBuf.get_iter_at_mark(startMark2)
				close = textBuf.get_iter_at_mark(closeMark2)
		return textBuf
		
	def insert_note_buf(self, textBuf, inBuf, mark, noteId):
		iter = textBuf.get_iter_at_mark(mark)
		iter.forward_char()
		final = textBuf.create_mark("final", iter, False)
		noteTag = "note" + str(noteId)
		print "Tag Here:" + noteTag
		textBuf.insert_with_tags(textBuf.get_iter_at_mark(mark), "</nl::noteInline::" + str(noteId) + ">",  self.tagTab.lookup("invisible"))
		textBuf.insert(textBuf.get_iter_at_mark(mark), "\n")
		textBuf.insert_with_tags(textBuf.get_iter_at_mark(mark), "END:" + self.noteDict[noteId][0],  self.tagTab.lookup("noteLink"), self.tagTab.lookup("visible"))
		textBuf.insert(textBuf.get_iter_at_mark(mark), "\n")
		textBuf.insert_with_tags(textBuf.get_iter_at_mark(mark), "</nl::noteInlineContent::" + str(noteId) + ">",  self.tagTab.lookup("invisible"))
		iter = textBuf.get_iter_at_mark(mark)
		iter.forward_char()
		endMark = textBuf.create_mark("endMark", iter, True)
		textBuf.insert_range(textBuf.get_iter_at_mark(mark), inBuf.get_start_iter(), inBuf.get_end_iter())
		iter = textBuf.get_iter_at_mark(endMark)
		iter.backward_char()
		textBuf.apply_tag(self.tagTab.lookup("visible"), textBuf.get_iter_at_mark(mark), iter)
		textBuf.insert_with_tags(textBuf.get_iter_at_mark(mark), "<nl::noteInline::" + str(noteId) + ">", self.tagTab.lookup("invisible"))
		textBuf.insert(textBuf.get_iter_at_mark(mark), "\n")
		return final
		
	def renderBlankState(self, body, head):
		print "here"
		glabel = gtk.Label()
		glabel.set_markup('<span size = "100">-Search-</span>')
		self.stateNotebook.set_tab_label_text(self.stateNotebook.get_nth_page(self.stateNotebook.get_current_page()), "Search")
		head.add(glabel)
		head.show_all()
		body.show_all()
		
	def renderViewState(self, body, head, viewId):
		viewStore = gtk.TreeStore(str, int, int, int)
		self.add_to_view_tree(viewStore, viewId, None)
		
		viewTree = gtk.TreeView(viewStore)
		viewTree.connect("row-activated", self.view_entry_clicked)
		cell = gtk.CellRendererText()
		col = gtk.TreeViewColumn("Entry")
		col.pack_start(cell, True)
		col.set_attributes(cell,text=0,id=1)
		viewTree.append_column(col)
		viewTree.show()
		
		noteList = self.get_view_notes(viewId)
		print noteList
		noteStore = gtk.ListStore(str, int)
		for noteId in noteList:
			noteStore.append([self.noteDict[noteId][0], noteId])
		
		noteTree = gtk.TreeView(noteStore)
		noteTree.connect("row-activated", self.clickFilter, 0)
		cell2 = gtk.CellRendererText()
		col2 = gtk.TreeViewColumn("Note")
		col2.pack_start(cell, True)
		col2.set_attributes(cell,text=0,id=1)
		noteTree.append_column(col2)
		noteTree.show()
		
		note = gtk.Notebook()
		noteLbl = gtk.Label("Note List")
		note.append_page(noteTree, noteLbl)
		viewLbl = gtk.Label("Entry")
		note.append_page(viewTree, viewLbl)
		body.add(note)
		body.show_all()
		
	def add_to_view_tree(self, store, viewId, parent):
		for row in self.viewMap[viewId]:
			print row
			name = self.tagList2[row[2]][0] if row[0] == 0 else self.viewDict[row[2]]
			iter = store.append(parent, [name, row[2], row[0], row[1]])
			if row[0] == 1:
				self.add_to_view_tree(store, row[2], iter)
		
	def view_entry_clicked(self, treeview, path, view_column):
		print "Clicked View Entry"
		
	def get_view_notes(self, viewId):
		groups = [[],[],[],[],[],[],[],[],[]]
		for row in self.viewMap[viewId]:
			print "Group:%i : %s" % (row[1], row[2])
			groups[row[1]].append(row)
		noteList = []
		for group in groups:
			if group != groups[0]:
				groupList = []
				for entry in group:
					print "Color: %s" % str(entry)
					if entry[0] == 0:
						if len(groupList) == 0:
							groupList.extend(self.tagMap[entry[2]][0])
							print groupList
						else:
							tagList = self.tagMap[entry[2]][0]
							for id in groupList:
								print "%s:%s:%s" % (str(id), str(tagList), str(groupList))
								if id not in tagList:
									groupList.remove(id)
					else:
						if len(groupList) == 0:
							groupList.extend(self.get_view_notes(entry[2]))
						else:
							viewList = self.get_view_notes(entry[2])
							for id in groupList:
								if id not in viewList:
									groupList.remove(id)
				noteList.extend(groupList)
			else:
				for entry in group:
					if entry[0] == 0:
						noteList.extend(self.tagMap[entry[2]][0])
					else:
						noteList.extend(self.get_view_notes(entry[2]))
		return list(set(noteList))
		
	def ViewFocusOut(self, textView, event, noteId):
		textBuf = gtk.TextBuffer(self.tagTab)
		clip = gtk.clipboard_get("BUFSTORE")
		textView.get_buffer().select_range(textView.get_buffer().get_start_iter(), textView.get_buffer().get_end_iter())
		textView.get_buffer().copy_clipboard(clip)
		textBuf.paste_clipboard(clip, None, True)
		textView.get_buffer().select_range(textView.get_buffer().get_end_iter(), textView.get_buffer().get_end_iter())
		self.file_from_buf(textBuf, noteId)
		
	def file_from_buf(self, textBuf, noteId):
		tags = []
		iter = textBuf.get_start_iter()
		print "Shucks:"
		print textBuf.get_text(textBuf.get_start_iter(), textBuf.get_end_iter())
		iter = textBuf.get_start_iter()
		while(1==1):
			print "looping!"
			tags = iter.get_tags()
			if self.tagTab.lookup("invisible") in tags:
				print "invisible!"
				iter2 = iter.copy()
				textOpen = iter.forward_search("<nl::noteLink>", gtk.TEXT_SEARCH_TEXT_ONLY)
				if textOpen != None:
					print "Dist: #####################"
					text = textBuf.get_text(iter2, textOpen[0])
					print len(text)
					if len(text) == 0:
						lineMark = textBuf.create_mark("lineMark", textOpen[0], False)
						textClose = iter.forward_search("</nl::noteLink>", gtk.TEXT_SEARCH_TEXT_ONLY)
						closeMark = textBuf.create_mark("endNoteLink", textClose[1], True)
						text = textBuf.get_text(textOpen[1], textClose[0]).split(",")
						inId = int(text[0])
						if int(text[1]) == 1:
							noteOpen = iter.forward_search("<nl::noteInline::" + str(inId) + ">", gtk.TEXT_SEARCH_TEXT_ONLY)
							markOpen0 = textBuf.create_mark("mark0", noteOpen[0])
							markOpen1 = textBuf.create_mark("mark1", noteOpen[1])
							noteEnd = iter.forward_search("</nl::noteInlineContent::" + str(inId) + ">", gtk.TEXT_SEARCH_TEXT_ONLY)
							markEnd = textBuf.create_mark("markEnd", noteEnd[0])
							noteClose = iter.forward_search("</nl::noteInline::" + str(inId) + ">", gtk.TEXT_SEARCH_TEXT_ONLY)
							markClose = textBuf.create_mark("markClose", noteClose[1])
							inBuf = gtk.TextBuffer(self.tagTab)
							inBuf.insert_range(inBuf.get_start_iter(), textBuf.get_iter_at_mark(markOpen1), textBuf.get_iter_at_mark(markEnd))
							self.file_from_buf(inBuf, inId)
							print "Test1: %s" % textBuf.get_text(textBuf.get_start_iter(), textBuf.get_end_iter())
							iter = textBuf.get_iter_at_mark(markClose)
							iter.forward_char()
							textBuf.delete(textBuf.get_iter_at_mark(markOpen0), iter)
							print "Test2: %s" % textBuf.get_text(textBuf.get_start_iter(), textBuf.get_end_iter())
							iter = textBuf.get_iter_at_mark(closeMark)
						iter = textBuf.get_iter_at_mark(lineMark)
						iter.set_line_offset(0)
						textBuf.delete(iter, textBuf.get_iter_at_mark(lineMark))
						iter = textBuf.get_iter_at_mark(closeMark)
			else:
				print "Visible!"
				markup = ""
				viewTag = ""
				for tag in tags:
					if iter.begins_tag(tag) and tag.get_property("name").find("viewLink") == 0:
						print "viewLink to file!"
						mark = textBuf.create_mark("temp", iter, True)
						while not iter.ends_tag(tag):
							iter.forward_to_tag_toggle(tag)
						iter.forward_char()
						textBuf.delete(textBuf.get_iter_at_mark(mark), iter)
						textBuf.insert(textBuf.get_iter_at_mark(mark),"<nl::viewLink>" + tag.get_property("name").lstrip("viewLink") + "</nl::viewLink>")
						iter = textBuf.get_iter_at_mark(mark)
						tags = iter.get_tags()
				for tag in tags:
					if iter.begins_tag(tag):
						if tag in self.toMarkup:
							markup += self.toMarkup[tag]
			if iter.ends_tag():
				for tag in self.toMarkup.keys():
					if iter.ends_tag(tag) and self.toMarkup[tag] not in inlineTags:
						print "Tag: " + self.toMarkup[tag]
						markup += self.toMarkup[tag].replace("<", "</")
			print "Markup: " + markup + " : " + str(len(markup))
			if len(markup) != 0:
				placeHolder = textBuf.create_mark("hold", iter ,False)
				textBuf.insert(iter, markup)
				iter = textBuf.get_iter_at_mark(placeHolder)
			else:
				iter.forward_char()
			if len(textBuf.get_text(iter, textBuf.get_end_iter())) == 0:
				break
			iter.forward_to_tag_toggle(None)
		fileOut = open("notes/" + self.noteDict[noteId][1], "w")
		fileOut.write(textBuf.get_text(textBuf.get_start_iter(), textBuf.get_end_iter()))
		
	def newDefaultState(self):
		self.newState("Search")
		
	def filterInput(self, widget, event):
		print "refiltering"
		self.tagFilter.refilter()
		self.viewFilter.refilter()
		self.noteFilter.refilter()
		
	def filterTags(self, widget, event):
		self.noteTagFilter.refilter()
		
	def checkSort(self, model, iter):
		if len(self.searchField.get_text()) == 0:
			return True
		search = self.searchField.get_text()
		value = model.get_value(iter, 0)
		return value.lower().find(search.lower()) != -1
		
	def text_insert(self, buffer, iter, text, length):
		end = iter.copy()
		iter.backward_chars(length)
		if self.bold.get_active():
			buffer.apply_tag_by_name('bold', iter, end)
		if self.red.get_active():
			buffer.apply_tag_by_name('red', iter, end)
		if self.ital.get_active():
			buffer.apply_tag_by_name('ital', iter, end)
		if self.titl.get_active():
			buffer.apply_tag_by_name('title', iter, end)
		
	def note_move_cursor_key(self, textview, step_size, count, extend_selection, temp, temp2):
		self.note_move_cursor(textview)
		
	def note_move_cursor_mouse(self, textview, event):
		print "Mouseing"
		self.note_move_cursor(textview)
		
	def note_move_cursor(self, textview):
		#buf = gtk.TextBuffer(self.tagTab)
		buf = textview.get_buffer()
		textBuf = textview.get_buffer()
		iter = buf.get_iter_at_offset(buf.get_property('cursor-position'))
		tags = iter.get_tags()
		for i in tags:
			name = i.get_property("name")
			page = self.stateNotebook.get_nth_page(self.stateNotebook.get_current_page())
			if name.find("tagP") == 0:
				id = int(name.lstrip("tagP"))
				textview.set_property("has-focus", False)
				page.pageState = [-1, id]
				self.renderState()
			if name.find("viewP") == 0:
				id = int(name.lstrip("viewP"))
				page.pageState = [-2, id]
				textview.set_property("has-focus", False)
				self.renderState()
		if self.tagTab.lookup("bold") in tags:
			self.bold.set_active(True)
		else:
			self.bold.set_active(False)
		if self.tagTab.lookup("red") in tags:
			self.red.set_active(True)
		else:
			self.red.set_active(False)
		if self.tagTab.lookup("ital") in tags:
			self.ital.set_active(True)
		else:
			self.ital.set_active(False)
		if self.tagTab.lookup("title") in tags:
			self.titl.set_active(True)
		else:
			self.titl.set_active(False)
		if self.tagTab.lookup("delMark") in tags:
			vl = None
			nl = None
			for i in tags:
				if i.get_property("name").find("viewLink") == 0: vl = i
			if vl != None:
				iter2 = iter.copy()
				iter.backward_to_tag_toggle(vl)
				iter2.forward_to_tag_toggle(vl)
				textBuf.delete(iter,iter2)
			else:
				startPos = iter.forward_search("<nl::noteLink>", gtk.TEXT_SEARCH_TEXT_ONLY)
				closePos = iter.forward_search("</nl::noteLink>", gtk.TEXT_SEARCH_TEXT_ONLY)
				iter = startPos[1].copy()
				iter.set_line_offset(0)
				open = textBuf.create_mark("open", iter, True)
				text = buf.get_text(startPos[1], closePos[0]).split(",")
				markClose = textBuf.create_mark("markClose", closePos[1])
				inId = int(text[0])
				if text[1] == '1':
					noteOpen = iter.forward_search("<nl::noteInline::" + str(inId) + ">", gtk.TEXT_SEARCH_TEXT_ONLY)
					markOpen0 = textBuf.create_mark("mark0", noteOpen[0])
					markOpen1 = textBuf.create_mark("mark1", noteOpen[1])
					noteEnd = iter.forward_search("</nl::noteInlineContent::" + str(inId) + ">", gtk.TEXT_SEARCH_TEXT_ONLY)
					markEnd = textBuf.create_mark("markEnd", noteEnd[0])
					noteClose = iter.forward_search("</nl::noteInline::" + str(inId) + ">", gtk.TEXT_SEARCH_TEXT_ONLY)
					markClose = textBuf.create_mark("markClose", noteClose[1])
					inBuf = gtk.TextBuffer(self.tagTab)
					inBuf.insert_range(inBuf.get_start_iter(), textBuf.get_iter_at_mark(markOpen1), textBuf.get_iter_at_mark(markEnd))
					self.file_from_buf(inBuf, inId)
				textBuf.delete(textBuf.get_iter_at_mark(open), textBuf.get_iter_at_mark(markClose))
		elif self.tagTab.lookup("expandMark") in tags:
			print "expand"
			iter2 = iter.copy()
			startPos = iter.forward_search("<nl::noteLink>", gtk.TEXT_SEARCH_TEXT_ONLY)
			closePos = iter.forward_search("</nl::noteLink>", gtk.TEXT_SEARCH_TEXT_ONLY)
			text = buf.get_text(startPos[1], closePos[0]).split(",")
			noteId = int(text[0])
			if noteId not in self.expNotes:
				textBuf.disconnect(self.focusCon)
				iter = iter2
				hold = buf.create_mark("hold", iter, True)
				iter2 = closePos[1]
				iter2.forward_char()
				endMark = buf.create_mark("noteInsert", iter2, True)
				textOpen = buf.create_mark("textOpen", startPos[1], True)
				textClose = buf.create_mark("textClose", closePos[0], False)
				buf.delete(startPos[1], closePos[0])
				buf.insert_with_tags(buf.get_iter_at_mark(textOpen), str(noteId) + ",1", self.tagTab.lookup("invisible"))
				iter = buf.get_iter_at_mark(hold)
				iter.backward_to_tag_toggle(self.tagTab.lookup("expandMark"))
				startIter = iter.copy()
				iter.forward_to_tag_toggle(self.tagTab.lookup("expandMark"))
				startMark = buf.create_mark("startTemp", startIter, True)
				buf.delete(startIter, iter)
				iter = buf.get_iter_at_mark(startMark)
				buf.insert_with_tags_by_name(iter, " [-]", "shrinkMark")
				textIn = self.buf_from_file("notes/" + self.noteDict[noteId][1])
				self.insert_note_buf(buf, textIn, endMark, noteId)
				self.expNotes.append(noteId)
				self.focusCon = textBuf.connect_after("insert-text", self.text_insert)
		elif self.tagTab.lookup("shrinkMark") in tags:
			print "shrink"
			textBuf.disconnect(self.focusCon)
			iter.backward_to_tag_toggle(self.tagTab.lookup("shrinkMark"))
			startIter = iter.copy()
			iter.forward_to_tag_toggle(self.tagTab.lookup("shrinkMark"))
			startMark = buf.create_mark("startTemp", startIter, True)
			print "Text: %s" % buf.get_text(startIter, iter)
			#buf.remove_all_tags(startIter, iter)
			buf.delete(startIter, iter)
			iter = buf.get_iter_at_mark(startMark)
			buf.insert_with_tags_by_name(iter, " [+]", "expandMark")
			startPos = iter.forward_search("<nl::noteLink>", gtk.TEXT_SEARCH_TEXT_ONLY)
			closePos = iter.forward_search("</nl::noteLink>", gtk.TEXT_SEARCH_TEXT_ONLY)
			text = buf.get_text(startPos[1], closePos[0]).split(",")
			noteId = int(text[0])
			self.expNotes.remove(noteId)
			print "Tag Here2: " + "note" + str(noteId)
			hold = buf.create_mark("hold", iter, True)
			textOpen = buf.create_mark("textOpen", startPos[1], True)
			textClose = buf.create_mark("textClose", closePos[0], False)
			buf.delete(startPos[1], closePos[0])
			buf.insert_with_tags(buf.get_iter_at_mark(textOpen), str(noteId) + ",0", self.tagTab.lookup("invisible"))
			iter = buf.get_iter_at_mark(hold)
			noteTag = self.tagTab.lookup("note" + str(noteId))
			startPos = iter.forward_search("<nl::noteInline::" + str(noteId) + ">", gtk.TEXT_SEARCH_TEXT_ONLY)
			contentPos = iter.forward_search("</nl::noteInlineContent::" + str(noteId) + ">", gtk.TEXT_SEARCH_TEXT_ONLY)
			endPos = iter.forward_search("</nl::noteInline::" + str(noteId) + ">", gtk.TEXT_SEARCH_TEXT_ONLY)
			iter = endPos[1]
			iter.forward_char()
			writeBuf = gtk.TextBuffer(self.tagTab)
			writeBuf.insert_range(writeBuf.get_start_iter(), startPos[1], contentPos[0])
			self.file_from_buf(writeBuf, noteId)
			buf.delete(startPos[0], iter)
			self.focusCon = textBuf.connect_after("insert-text", self.text_insert)
		elif self.tagTab.lookup("noteLink") in tags:
			startPos = iter.forward_search("<nl::noteLink>", gtk.TEXT_SEARCH_TEXT_ONLY)
			closePos = iter.forward_search("</nl::noteLink>", gtk.TEXT_SEARCH_TEXT_ONLY)
			text = buf.get_text(startPos[1], closePos[0]).split(",")
			id = int(text[0])
			textview.set_property("has-focus", False)
			page.pageState = [0, id]
			self.renderState()
			
	def format_button_toggled(self, button, form):
		print "Do I still need this?"

test = NotesCore()
gtk.main()