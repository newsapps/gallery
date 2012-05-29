(function($) {

var settings = window.gallerySettings,
    _gaq = window._gaq;
    _gaq.push(['_setAccount', 'UA-9792248-9']);
    _gaq.push(['_setDomainName', 'chicagotribune.com']);

function travelling_nav() {
    var thumbHeight = $($("#sheet .thumb")[0]).outerHeight(true);
    $(".thumb img").removeClass("selected");
    if ($("#traveller").offset().top < $(window).scrollTop()) {
        $("#boom").removeClass("cleated");
        $($("#photos .photo-wrapper").get().reverse()).each(function(i,p){
            var photo = $(p);
            if($(window).scrollTop() > photo.offset().top ){
                var visiblePx = photo.outerHeight() + photo.offset().top - $(window).scrollTop();
                var visiblePct = visiblePx / photo.outerHeight();
                var sheetAdjustment = ($("#photos .photo-wrapper").length - i) * thumbHeight - visiblePct * thumbHeight;
                $("#sheet").css("margin-top", -(sheetAdjustment));
                $("#thumb-" + p.id + " img").addClass("selected");
                return false;
            }
        });
    } else {
        $("#sheet").css("margin-top", 0);
        $("#boom").addClass("cleated");
    }
}

function change_hash() {
    var newhash, newphoto;
    var bodyPadding = parseInt($("body").css("padding-top").replace("px",""));
    if ($("#traveller").offset().top < $(window).scrollTop()) {
        $($("#photos .photo-wrapper").get().reverse()).each(function(i,p){
            var photo = $(p);
            if( ($(window).scrollTop() + bodyPadding + (photo.height() /2 )) > photo.offset().top ){
                newphoto = photo;
                newhash = photo.attr('id'); 
                return false;
            }
        });
    } else {
        newhash = "1";
        newphoto = $("#photos #1")
    }

    if (newhash && newhash != '1' && window.location.hash != '#' + newhash) {
        newphoto.attr('id', 'tmp-' + newhash);
        window.location.hash = newhash;
        newphoto.attr('id', newhash);
        
        var href = newphoto.find('.fb-like').attr('data-href');
        rotate_ad($('#ad'), href, newhash);
    }
}

function rotate_ad(target, href, hash) {
    var target, url = '', 
        title = settings.title,
        url = href || window.location.href,
        u = "u=" + url + ';',
        ord = "ord=" + (Math.random() * 1000000000000000) + "?",
        ad_url = "http://ad.doubleclick.net/adi/trb.chicagotribune/" + settings.section + ";tile=2;ptype=sf;dcopt=ist;pos=1;sz=300x250;" + u + ord;
   
    target.attr('src', ad_url);
    
    s.pageName="Photo gallery "+ title +" -- News application, 3rd Party"
    if (title) {
        s.prop37 = title +" photo #"+ hash; 
    }
    
    s.events = "";
    void(s.t());
    _gaq.push(['_trackPageview', window.location]);
}

function calculate_layout() {
  var bodyPadding = parseInt($("body").css("padding-top").replace("px","")),
      footerHeight = $('#footer').outerHeight(),
      photoHeight = $('#photos .photo:last-child').height(),
      extra = $(window).height() - footerHeight - bodyPadding - photoHeight;
  
  extra = (extra > 0) ? extra : 0;
  $('#photos').css('margin-bottom', extra);

  $('#photos .photo').each(function() {
    var height = $('img.fullsize', this).height();
    $('a.nav', this).css({
      'height' : height + 'px'
    });
  });

}

function adapt_images() {
    $('noscript[data-phone-url][data-tablet-url][data-desktop-url]').each(function() {
        var w = $(window).width(), src;
        if      (w <= 480)       { src = $(this).data('phone-url');   }
        else if (w <= 1178)      { src = $(this).data('tablet-url');  } // 300 (ad) + 110 (padding) + 768 (photo)
        else if (w <= 1434)      { src = $(this).data('desktop-url'); } // 300 (ad) + 110 (padding) + 1024 (photo)
        else                     { src = $(this).data('full-url');    } // 300 (ad) + 110 (padding) + 1280 (photo)

        if ($(this).next().is('img.fullsize')) {
            $(this).next().attr('src', src);
        }
        else {
            $('<img class="fullsize" src="' + src + '" alt="' + $(this).data('alt') + '" />').insertAfter($(this));
        }
    });
}

$(document).ready(function(){
    
    $('.link').click(function(e){
        $('#link input').val($(this).attr('href'));
        $('#link').modal();
        $('#link input').select();
        return false;
    });
    
    var lazy_change_hash = _.debounce(change_hash, 2000),
        lazy_adapt_images = _.debounce(adapt_images, 500);

    adapt_images();
    travelling_nav();
    rotate_ad($('#ad'));

    $(window).scroll(travelling_nav);
    $(window).scroll(lazy_change_hash);
    $(window).resize(calculate_layout);
    $(window).resize(lazy_adapt_images);

    $("a.smooth").smoothScroll();

    // Last image must be loaded to calculate layout
    $('#photos .photo:last-child img').load(function() {
      calculate_layout();
    });
    
});

})(jQuery);
