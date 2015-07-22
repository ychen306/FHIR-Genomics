// copied from http://stackoverflow.com/questions/8389646/send-post-data-on-redirect-with-javascript-jquery 
$.extend({
  redirectPost: function(location, args) {
                  var form = '';
                  $.each( args, function( key, value ) {
                    value = value.split('"').join('\"')
                    form += '<input type="hidden" name="'+key+'" value="'+value+'">';
                  });
                  $('<form action="' + location + '" method="POST">' + form + '</form>').appendTo($(document.body)).submit();
                }
}); 

// Prompt user to select resource(s) and create a context with selected resources
var resourceTypes = Object.keys(resources);
var typeToPrompt;
var selected = {};
var promptSelection = function () {
    typeToPrompt = resourceTypes.pop();
    var display = '<ul class="list-group">';
    for (var i = 0; i < resources[typeToPrompt].length; i++) { 
        var res = resources[typeToPrompt][i];
        display += '<a class="list-group-item" href="#" resource-id="'+res.id+'">'+typeToPrompt+' - '+res.desc+'</a>';
    }
    display += "</ul>";
    $('#launch-prompt').html(display);
    $('.list-group-item').click(function() { 
      selected[typeToPrompt] = $(this).attr('resource-id');
      if (resourceTypes.length > 0) { 
        promptSelection();
      } else {
        $.redirectPost(cont_url, selected);
      }
    });
};
$(document).ready(promptSelection);
